type LogoutListener = () => void;

const listeners = new Set<LogoutListener>();

export function onLogout(listener: LogoutListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function emitLogout(): void {
  listeners.forEach((listener) => listener());
}