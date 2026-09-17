import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type Ctx = {
  count: number;
  setCount: (n: number) => void;
  openCheckout: () => void;
  setOpenCheckout: (fn: () => void) => void;
};

const SelectionContext = createContext<Ctx>({
  count: 0,
  setCount: () => {},
  openCheckout: () => {},
  setOpenCheckout: () => {},
});

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [count, setCount] = useState(0);
  const opener = useRef<() => void>(() => {});

  const openCheckout = useCallback(() => opener.current(), []);
  const setOpenCheckout = useCallback((fn: () => void) => {
    opener.current = fn;
  }, []);

  const value = useMemo<Ctx>(
    () => ({ count, setCount, openCheckout, setOpenCheckout }),
    [count, openCheckout, setOpenCheckout],
  );

  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>;
}

export const useSelection = () => useContext(SelectionContext);
