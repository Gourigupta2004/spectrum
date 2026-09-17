import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type IntroCtx = {
  /** Nav renders its logomark only once the intro logo has handed off. */
  navLogoVisible: boolean;
  setNavLogoVisible: (v: boolean) => void;
  /** Site chrome + page content stay mounted but invisible while the intro plays. */
  contentHidden: boolean;
  setContentHidden: (v: boolean) => void;
};

const Ctx = createContext<IntroCtx>({
  navLogoVisible: true,
  setNavLogoVisible: () => {},
  contentHidden: false,
  setContentHidden: () => {},
});

export function IntroProvider({
  children,
  initialContentHidden = false,
}: {
  children: ReactNode;
  initialContentHidden?: boolean;
}) {
  const [navLogoVisible, setNavLogoVisible] = useState(true);
  const [contentHidden, setContentHidden] = useState(initialContentHidden);
  const value = useMemo(
    () => ({ navLogoVisible, setNavLogoVisible, contentHidden, setContentHidden }),
    [navLogoVisible, contentHidden],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useIntro = () => useContext(Ctx);
