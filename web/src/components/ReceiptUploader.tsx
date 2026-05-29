/**
 * ReceiptUploader — drag-and-drop receipt upload component.
 *
 * Upload flow:
 *   1. User drops or selects a file (JPEG / PNG / PDF).
 *   2. POST /receipts/upload-url → {receipt_id, upload_url, object_key}
 *   3. Browser PUTs the file directly to S3 via upload_url (no API proxy).
 *   4. POST /receipts/{receipt_id}/confirm with byte_size.
 *   5. Poll GET /receipts/{receipt_id} every 2s until status ≠ PROCESSING.
 *   6. Call onReceiptReady(receipt_id) so parent can attach it to the transaction.
 */
import { useCallback, useRef, useState } from "react";
import axios from "axios";
import { api } from "@/lib/api";
import type { Receipt, UploadUrlResponse } from "@/types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type UploadStage =
  | "idle"
  | "requesting_url"
  | "uploading"
  | "confirming"
  | "polling"
  | "done"
  | "error";

const ACCEPTED_TYPES = ["image/jpeg", "image/jpg", "image/png", "application/pdf"];
const ACCEPTED_EXTENSIONS = ".jpg,.jpeg,.png,.pdf";
const MAX_BYTES = 10 * 1024 * 1024; // 10 MB

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function stageCopy(stage: UploadStage): string {
  switch (stage) {
    case "requesting_url": return "Getting upload URL…";
    case "uploading":      return "Uploading to storage…";
    case "confirming":     return "Confirming upload…";
    case "polling":        return "Processing receipt…";
    case "done":           return "Receipt attached";
    default:               return "";
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface ReceiptUploaderProps {
  onReceiptReady: (receiptId: string) => void;
  onClear: () => void;
}

export function ReceiptUploader({ onReceiptReady, onClear }: ReceiptUploaderProps) {
  const [stage, setStage] = useState<UploadStage>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [receiptStatus, setReceiptStatus] = useState<Receipt["status"] | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const reset = useCallback(() => {
    if (pollTimer.current) clearTimeout(pollTimer.current);
    setStage("idle");
    setErrorMsg(null);
    setFileName(null);
    setReceiptStatus(null);
    onClear();
    if (inputRef.current) inputRef.current.value = "";
  }, [onClear]);

  const upload = useCallback(
    async (file: File) => {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setErrorMsg("Only JPEG, PNG, and PDF files are accepted.");
        setStage("error");
        return;
      }
      if (file.size > MAX_BYTES) {
        setErrorMsg(`File too large — max ${humanSize(MAX_BYTES)}.`);
        setStage("error");
        return;
      }

      setFileName(file.name);
      setErrorMsg(null);

      // Step 1 — request presigned PUT URL
      let receiptId: string;
      let uploadUrl: string;
      try {
        setStage("requesting_url");
        const { data } = await api.post<UploadUrlResponse>("/receipts/upload-url", {
          content_type: file.type,
        });
        receiptId = data.receipt_id;
        uploadUrl = data.upload_url;
      } catch {
        setErrorMsg("Could not get upload URL — check your connection.");
        setStage("error");
        return;
      }

      // Step 2 — PUT directly to S3 (no auth header — presigned URL is self-contained)
      try {
        setStage("uploading");
        await axios.put(uploadUrl, file, {
          headers: { "Content-Type": file.type },
        });
      } catch {
        setErrorMsg("Upload to storage failed — please try again.");
        setStage("error");
        return;
      }

      // Step 3 — confirm the upload so the backend enqueues OCR
      try {
        setStage("confirming");
        await api.post(`/receipts/${receiptId}/confirm`, { byte_size: file.size });
      } catch {
        setErrorMsg("Failed to confirm upload — please retry.");
        setStage("error");
        return;
      }

      // Step 4 — poll until OCR finishes (or fails)
      setStage("polling");
      const poll = async () => {
        try {
          const { data: receipt } = await api.get<Receipt>(`/receipts/${receiptId}`);
          setReceiptStatus(receipt.status);

          if (receipt.status === "PROCESSING") {
            // Still in flight — check again in 2 s
            pollTimer.current = setTimeout(poll, 2000);
          } else {
            // Terminal state
            setStage("done");
            // H5: only attach the receipt when OCR succeeded or needs review.
            // A FAILED receipt has extracted_data=null — attaching it would
            // link null data to the transaction silently.
            if (receipt.status === "COMPLETED" || receipt.status === "NEEDS_REVIEW") {
              onReceiptReady(receiptId);
            }
            // FAILED: shown in UI with error styling but not attached
          }
        } catch {
          setErrorMsg("Lost track of receipt status — try attaching again.");
          setStage("error");
        }
      };
      poll();
    },
    [onReceiptReady]
  );

  // Drop handler
  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) upload(file);
    },
    [upload]
  );

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) upload(file);
    },
    [upload]
  );

  // ------------------------------------------------------------------ render

  if (stage === "idle" || stage === "error") {
    return (
      <div>
        <label className="block text-sm font-medium text-[#0c0a08] mb-1">
          Receipt <span className="text-[#6e6a68] font-normal">(optional)</span>
        </label>
        <div
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center justify-center gap-1 border-2 border-dashed border-[#d2cecb] rounded-lg px-4 py-5 cursor-pointer hover:border-[#6e6a68] hover:bg-[#f4f2f0] transition-colors"
        >
          <span className="text-2xl">📎</span>
          <p className="text-sm text-[#6e6a68]">
            Drag and drop or{" "}
            <span className="underline text-[#0c0a08]">browse</span>
          </p>
          <p className="text-xs text-[#6e6a68]">JPEG, PNG, PDF · max 10 MB</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          className="hidden"
          onChange={onFileChange}
        />
        {stage === "error" && errorMsg && (
          <p className="mt-1.5 text-xs text-red-600">{errorMsg}</p>
        )}
      </div>
    );
  }

  if (stage === "done") {
    const statusColor =
      receiptStatus === "COMPLETED"
        ? "text-green-700 bg-green-50 border-green-200"
        : receiptStatus === "NEEDS_REVIEW"
        ? "text-yellow-700 bg-yellow-50 border-yellow-200"
        : receiptStatus === "FAILED"
        ? "text-red-700 bg-red-50 border-red-200"
        : "text-[#6e6a68] bg-[#f4f2f0]";

    return (
      <div>
        <label className="block text-sm font-medium text-[#0c0a08] mb-1">Receipt</label>
        <div className={`flex items-center justify-between rounded-lg border px-3 py-2 ${statusColor}`}>
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-base flex-shrink-0">
              {receiptStatus === "COMPLETED" ? "✅" : receiptStatus === "FAILED" ? "❌" : "⚠️"}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{fileName}</p>
              <p className="text-xs opacity-75">
                {receiptStatus === "COMPLETED"
                  ? "OCR complete — data extracted"
                  : receiptStatus === "NEEDS_REVIEW"
                  ? "Low confidence — you can review after creation"
                  : receiptStatus === "FAILED"
                  ? "OCR failed — fill in details manually"
                  : receiptStatus}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={reset}
            className="ml-3 flex-shrink-0 text-xs underline opacity-70 hover:opacity-100"
          >
            Remove
          </button>
        </div>
      </div>
    );
  }

  // In-progress states: requesting_url / uploading / confirming / polling
  return (
    <div>
      <label className="block text-sm font-medium text-[#0c0a08] mb-1">Receipt</label>
      <div className="flex items-center gap-3 rounded-lg border border-[#d2cecb] px-3 py-3 bg-[#f4f2f0]">
        <div className="flex-shrink-0 w-4 h-4 border-2 border-[#d2cecb] border-t-[#0c0a08] rounded-full animate-spin" />
        <div className="min-w-0">
          <p className="text-sm text-[#0c0a08] truncate">{fileName}</p>
          <p className="text-xs text-[#6e6a68]">{stageCopy(stage)}</p>
        </div>
      </div>
    </div>
  );
}
