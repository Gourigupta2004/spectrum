import { useSyncExternalStore } from "react";
import { captionItems, type CaptionItem } from "./caption-data";
import { seedNames } from "./student-data";

export type Store<T> = {
  get: () => T;
  set: (updater: T | ((prev: T) => T)) => void;
  subscribe: (fn: () => void) => () => void;
};

export function createStore<T>(initial: T): Store<T> {
  let value = initial;
  const subs = new Set<() => void>();
  return {
    get: () => value,
    set: (updater) => {
      value = typeof updater === "function" ? (updater as (p: T) => T)(value) : updater;
      subs.forEach((fn) => fn());
    },
    subscribe: (fn) => {
      subs.add(fn);
      return () => subs.delete(fn);
    },
  };
}

/** Decorative session flag for the institution portal. */
export const sessionStore = createStore(false);

/** Caption workspace items — shared so the branch screen can count pending work. */
export const captionStore = createStore<CaptionItem[]>(captionItems);

/** studentId -> typed name. In memory only; a refresh resets the demo. */
export const namesStore = createStore<Record<string, string>>({ ...seedNames });

export function useStore<T>(store: Store<T>): T {
  return useSyncExternalStore(store.subscribe, store.get, store.get);
}

/**
 * For stores seeded from localStorage and read on server-rendered pages (the
 * nav): the server and the hydrating client both see `serverValue`, then the
 * real value takes over — so a remembered login never causes a hydration
 * mismatch.
 */
export function useClientStore<T>(store: Store<T>, serverValue: T): T {
  return useSyncExternalStore(store.subscribe, store.get, () => serverValue);
}
