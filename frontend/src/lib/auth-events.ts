type Listener = () => void;

const logoutListeners = new Set<Listener>();
const loginListeners = new Set<Listener>();

export function onLogout(listener: Listener): () => void {
  logoutListeners.add(listener);
  return () => {
    logoutListeners.delete(listener);
  };
}

export function emitLogout(): void {
  logoutListeners.forEach((listener) => listener());
}

export function onLogin(listener: Listener): () => void {
  loginListeners.add(listener);
  return () => {
    loginListeners.delete(listener);
  };
}

export function emitLogin(): void {
  loginListeners.forEach((listener) => listener());
}