/**
 * Portal data hooks. Each one reads from the API when VITE_API_URL is set and from
 * the in-memory demo stores otherwise, so the workspace screens don't branch.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { hasApi } from "./api";
import {
  byMomentTitle,
  captionItems as seedItems,
  todayLabel,
  type CaptionItem,
  type CaptionStatus,
} from "./caption-data";
import { authStore, portalFetch } from "./portal-session";
import { captionStore, namesStore, useStore } from "./portal-store";
import {
  classes as demoClasses,
  findClass,
  studentsOf,
  totalStudents,
  type SchoolClass,
  type Student,
} from "./student-data";

export type ClassSummary = SchoolClass & { named: number };

const NO_STUDENTS: Student[] = [];
const NO_ITEMS: CaptionItem[] = [];

/**
 * Whose data this is. Every cache key carries it, so one login can never read
 * what another left behind — which is what the portal layout used to achieve by
 * emptying the cache in an effect. That effect ran as its own children were
 * mounting, so it threw away their in-flight request and the screens sat on
 * "Loading…" forever. Scoping the keys gets the same isolation without
 * cancelling anything.
 */
const owner = (): string | number => authStore.get()?.member.id ?? "demo";

const keys = {
  captions: () => ["portal", owner(), "captions"] as const,
  classes: () => ["portal", owner(), "classes"] as const,
  roster: (id: string) => ["portal", owner(), "class", id] as const,
  summary: () => ["portal", owner(), "summary"] as const,
};

const signedIn = () => authStore.get() !== null;

/* ------------------------------------------------------------------ captions */

export function useCaptionItems(): { items: CaptionItem[]; loading: boolean; error: string } {
  const demo = useStore(captionStore);
  const query = useQuery({
    queryKey: keys.captions(),
    queryFn: () =>
      portalFetch<{ items: CaptionItem[] }>("/api/portal/captions/").then((r) => r.items),
    enabled: hasApi && signedIn(),
  });
  // Always shown in file-name order (alphabetical + numerical), whatever order
  // the rows arrived in — the same order the admin table uses.
  const raw = hasApi ? (query.data ?? NO_ITEMS) : demo;
  const items = useMemo(() => [...raw].sort(byMomentTitle), [raw]);
  if (!hasApi) return { items, loading: false, error: "" };
  return {
    items,
    loading: query.isPending,
    error: query.error instanceof Error ? query.error.message : "",
  };
}

type Resolve = (
  id: string,
  status: CaptionStatus,
  patch: Partial<CaptionItem>,
  by: string,
  phone: string,
) => void;

export function useResolveCaption(): { resolve: Resolve; error: string } {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const mutation = useMutation({
    mutationFn: (v: {
      id: string;
      status: CaptionStatus;
      patch: Partial<CaptionItem>;
      by: string;
      phone: string;
    }) =>
      portalFetch<CaptionItem>(`/api/portal/captions/${v.id}/resolve/`, {
        method: "POST",
        json: {
          status: v.status,
          text: v.patch.caption ?? v.patch.correction ?? "",
          actionBy: v.by,
          actionByPhone: v.phone,
        },
      }),
    onMutate: async (v) => {
      setError("");
      await client.cancelQueries({ queryKey: keys.captions() });
      const previous = client.getQueryData<CaptionItem[]>(keys.captions());
      client.setQueryData<CaptionItem[]>(keys.captions(), (items = []) =>
        items.map((i) =>
          i.id === v.id
            ? {
                ...i,
                ...v.patch,
                status: v.status,
                actionBy: v.by,
                actionByPhone: v.phone,
                updatedAt: todayLabel(),
              }
            : i,
        ),
      );
      return { previous };
    },
    onError: (err, _v, context) => {
      if (context?.previous) client.setQueryData(keys.captions(), context.previous);
      setError(err instanceof Error ? err.message : "Could not save. Please try again.");
    },
    onSuccess: (item) => {
      client.setQueryData<CaptionItem[]>(keys.captions(), (items = []) =>
        items.map((i) => (i.id === item.id ? item : i)),
      );
      client.invalidateQueries({ queryKey: keys.summary() });
    },
  });

  const resolve = useCallback<Resolve>(
    (id, status, patch, by, phone) => {
      if (!hasApi) {
        captionStore.set((prev) =>
          prev.map((i) =>
            i.id === id
              ? {
                  ...i,
                  ...patch,
                  status,
                  actionBy: by,
                  actionByPhone: phone,
                  updatedAt: todayLabel(),
                }
              : i,
          ),
        );
        return;
      }
      mutation.mutate({ id, status, patch, by, phone });
    },
    [mutation],
  );
  return { resolve, error };
}

/** Replace a caption item's photo (Spectrum team only). Shows the local file at once. */
export function useReplaceCaptionImage() {
  const client = useQueryClient();
  return useCallback(
    async (id: string, file: File) => {
      const preview = URL.createObjectURL(file);
      if (!hasApi) {
        const previous = captionStore.get().find((i) => i.id === id)?.image;
        captionStore.set((prev) => prev.map((i) => (i.id === id ? { ...i, image: preview } : i)));
        if (previous?.startsWith("blob:")) URL.revokeObjectURL(previous);
        return;
      }
      const previous = client
        .getQueryData<CaptionItem[]>(keys.captions())
        ?.find((i) => i.id === id)?.image;
      const setImage = (image: string) =>
        client.setQueryData<CaptionItem[]>(keys.captions(), (items = []) =>
          items.map((i) => (i.id === id ? { ...i, image } : i)),
        );
      setImage(preview);
      const body = new FormData();
      body.append("image", file);
      try {
        const item = await portalFetch<CaptionItem>(`/api/portal/captions/${id}/image/`, {
          method: "POST",
          body,
        });
        // The worker may still be making the web copy; keep the local file until then.
        setImage(item.image || preview);
        if (item.image) URL.revokeObjectURL(preview);
        else scheduleRefetch(client);
      } catch (error) {
        setImage(previous ?? "");
        URL.revokeObjectURL(preview);
        throw error;
      }
    },
    [client],
  );
}

/** New uploads are processed in the background; pick them up once that is done. */
function scheduleRefetch(client: ReturnType<typeof useQueryClient>) {
  window.setTimeout(() => void client.invalidateQueries({ queryKey: keys.captions() }), 4000);
}

export type NewCaption = {
  file: File | null;
  title: string;
  caption: string;
  requested: CaptionStatus;
};

/** Add a photo to the caption workspace (Spectrum team only). */
export function useAddCaption() {
  const client = useQueryClient();
  return useCallback(
    async (input: NewCaption) => {
      if (!hasApi) {
        captionStore.set((prev) => [
          {
            id: `c-${Date.now()}`,
            momentTitle: input.title,
            image: input.file ? URL.createObjectURL(input.file) : seedItems[0]!.image,
            caption: input.caption,
            requested: input.requested as CaptionItem["requested"],
            status: input.requested,
            updatedAt: todayLabel(),
          },
          ...prev,
        ]);
        return;
      }
      if (!input.file) throw new Error("Choose an image.");
      const body = new FormData();
      body.append("image", input.file);
      body.append("momentTitle", input.title);
      body.append("caption", input.caption);
      body.append("requested", input.requested);
      const item = await portalFetch<CaptionItem>("/api/portal/captions/", {
        method: "POST",
        body,
      });
      const local = { ...item, image: item.image || URL.createObjectURL(input.file) };
      client.setQueryData<CaptionItem[]>(keys.captions(), (items = []) => [local, ...items]);
      client.invalidateQueries({ queryKey: keys.summary() });
      if (!item.image) scheduleRefetch(client);
    },
    [client],
  );
}

/* ------------------------------------------------------------------ workspace summary */

export function useWorkspaceSummary(): { pending: number; named: number; total: number } {
  const demoItems = useStore(captionStore);
  const demoNames = useStore(namesStore);
  const query = useQuery({
    queryKey: keys.summary(),
    queryFn: () =>
      portalFetch<{ pendingCaptions: number; students: number; named: number }>(
        "/api/portal/summary/",
      ),
    enabled: hasApi && signedIn(),
  });
  if (hasApi) {
    return {
      pending: query.data?.pendingCaptions ?? 0,
      named: query.data?.named ?? 0,
      total: query.data?.students ?? 0,
    };
  }
  return {
    pending: demoItems.filter((i) => i.status !== "approved" && i.status !== "corrected").length,
    named: Object.values(demoNames).filter((n) => n.trim().length > 0).length,
    total: totalStudents,
  };
}

/* ------------------------------------------------------------------ classes & students */

export function useClassList(): { classes: ClassSummary[]; loading: boolean; error: string } {
  const names = useStore(namesStore);
  const query = useQuery({
    queryKey: keys.classes(),
    queryFn: () =>
      portalFetch<{ classes: (SchoolClass & { namedCount: number })[] }>(
        "/api/portal/classes/",
      ).then((r) => r.classes.map((c) => ({ ...c, named: c.namedCount }))),
    enabled: hasApi && signedIn(),
  });
  const demo = useMemo(
    () =>
      demoClasses.map((c) => ({
        ...c,
        named: Object.entries(names).filter(
          ([k, v]) => k.startsWith(`${c.id}-`) && v.trim().length > 0,
        ).length,
      })),
    [names],
  );
  if (!hasApi) return { classes: demo, loading: false, error: "" };
  return {
    classes: query.data ?? [],
    loading: query.isPending,
    error: query.error instanceof Error ? query.error.message : "",
  };
}

type Roster = { cls: SchoolClass | undefined; students: Student[]; loading: boolean };

export function useRoster(classId: string): Roster {
  const query = useQuery({
    queryKey: keys.roster(classId),
    queryFn: () =>
      portalFetch<{ class: SchoolClass; students: Student[] }>(
        `/api/portal/classes/${encodeURIComponent(classId)}/`,
      ),
    enabled: hasApi && signedIn(),
    retry: (count, error) =>
      !(error instanceof Error && /not found/i.test(error.message)) && count < 2,
    staleTime: Infinity, // names are kept locally while the page is open
  });
  const demoCls = useMemo(() => (hasApi ? undefined : findClass(classId)), [classId]);
  const demoStudents = useMemo(() => (demoCls ? studentsOf(demoCls.id) : []), [demoCls]);
  if (!hasApi) return { cls: demoCls, students: demoStudents, loading: false };
  return {
    cls: query.data?.class,
    students: query.data?.students ?? NO_STUDENTS,
    loading: query.isPending,
  };
}

const FLUSH_MS = 600;

/**
 * Student names for one class. Typing commits locally at once (so Enter-to-next
 * stays instant); with the backend, commits are batched into one request shortly
 * after the last change and flushed when the page is left.
 */
export function useStudentNames(classId: string, students: Student[]) {
  const demoNames = useStore(namesStore);
  const client = useQueryClient();
  const [names, setNames] = useState<Record<string, string>>({});
  const latest = useRef<Record<string, string>>({});
  const pending = useRef<Record<string, string>>({});
  const timer = useRef<number | null>(null);

  const lastClass = useRef(classId);
  useEffect(() => {
    if (!hasApi) return;
    if (lastClass.current !== classId) {
      // Unsent names belong to the previous class; never send them to this one.
      lastClass.current = classId;
      pending.current = {};
    }
    if (students === NO_STUDENTS) return;
    const initial = Object.fromEntries(students.map((s) => [s.id, s.name]));
    latest.current = { ...initial, ...pending.current };
    setNames(latest.current);
  }, [classId, students]);

  const flush = useCallback(
    (keepalive = false) => {
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = null;
      const batch = pending.current;
      if (!Object.keys(batch).length) return Promise.resolve();
      pending.current = {};
      return portalFetch<{ namedCount: number }>(
        `/api/portal/classes/${encodeURIComponent(classId)}/names/`,
        {
          method: "PUT",
          json: { names: batch },
          keepalive,
        },
      )
        .then(() => {
          client.setQueryData<{ class: SchoolClass; students: Student[] }>(
            keys.roster(classId),
            (data) =>
              data
                ? {
                    ...data,
                    students: data.students.map((s) =>
                      s.id in batch ? { ...s, name: batch[s.id]! } : s,
                    ),
                  }
                : data,
          );
          client.invalidateQueries({ queryKey: keys.classes() });
          client.invalidateQueries({ queryKey: keys.summary() });
        })
        .catch(() => {
          // Keep the unsaved names and try again with the next change.
          pending.current = { ...batch, ...pending.current };
        });
    },
    [classId, client],
  );

  useEffect(() => {
    if (!hasApi) return;
    const onHide = () => void flush(true);
    window.addEventListener("pagehide", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      void flush(true);
    };
  }, [flush]);

  const commit = useCallback(
    (studentId: string, value: string) => {
      if (!hasApi) {
        namesStore.set((prev) => ({ ...prev, [studentId]: value }));
        return;
      }
      latest.current = { ...latest.current, [studentId]: value };
      pending.current[studentId] = value;
      setNames(latest.current);
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => void flush(), FLUSH_MS);
    },
    [flush],
  );

  /** Names as of right now, including a commit that happened in this same tick. */
  const current = useCallback(() => (hasApi ? latest.current : namesStore.get()), []);

  return { names: hasApi ? names : demoNames, commit, current, flush };
}
