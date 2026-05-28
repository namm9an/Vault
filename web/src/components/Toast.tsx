import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

type ToastType = "error" | "success" | "info";

interface ToastMsg {
  id: number;
  type: ToastType;
  message: string;
}

const ToastCtx = createContext<{ toast: (type: ToastType, message: string) => void }>({
  toast: () => {},
});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMsg[]>([]);

  const toast = useCallback((type: ToastType, message: string) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  const colors: Record<ToastType, string> = {
    error: "bg-red-600",
    success: "bg-green-600",
    info: "bg-neutral-800",
  };

  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`${colors[t.type]} text-white text-sm px-4 py-3 rounded-lg shadow-lg max-w-sm`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const { toast } = useContext(ToastCtx);
  return {
    error: (msg: string) => toast("error", msg),
    success: (msg: string) => toast("success", msg),
    info: (msg: string) => toast("info", msg),
  };
}
