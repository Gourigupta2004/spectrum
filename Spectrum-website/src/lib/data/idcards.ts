import { apiFetch, hasApi } from "../api";
import { idCardCopy, type IdCardCopy } from "./defaults";
import { checkout, type Payable } from "./orders";
import type { Seo } from "./site";

/** An institution that offers duplicate ID cards, at its own price per card (₹). */
export type IdCardInstitution = { id: string; name: string; price: number };

export type IdCardData = {
  seo: Seo;
  copy: IdCardCopy;
  /** The choices under "Type of card" and "Color of Lanyard", set in the admin; a dropdown with none is hidden. */
  cardTypes: string[];
  lanyardColours: string[];
  institutions: IdCardInstitution[];
};

export type DuplicateIdCardInput = {
  institutionId: string;
  studentName: string;
  className: string;
  admissionNo: string;
  cardType: string;
  lanyardColour: string;
  email: string;
  phone: string;
  idempotencyKey: string;
};

export type DuplicateIdCardRequest = Payable & {
  publicId: string;
  status: "created" | "paid" | "shipped" | "failed";
  amount: number;
};

export async function getIdCardPage(): Promise<IdCardData> {
  if (hasApi) {
    const data = await apiFetch<IdCardData>("/api/pages/id-card/");
    return {
      ...data,
      copy: { ...idCardCopy, ...data.copy },
      cardTypes: data.cardTypes ?? [],
      lanyardColours: data.lanyardColours ?? [],
    };
  }
  return {
    seo: {
      title: "Duplicate ID Card — Spectrum",
      description: "Request a duplicate student ID card and pay online.",
    },
    copy: idCardCopy,
    cardTypes: ["Student", "Parent"],
    lanyardColours: ["Blue", "Red", "Yellow", "Green"],
    institutions: [
      { id: "dps", name: "Delhi Public School", price: 150 },
      { id: "ryan", name: "Ryan International School", price: 120 },
    ],
  };
}

/**
 * Creates the request at the institution's price, opens Razorpay Checkout and
 * verifies the payment. Resolves with the paid request, or null if the window
 * was closed.
 */
export async function payForDuplicateIdCard(
  input: DuplicateIdCardInput,
  description: string,
): Promise<DuplicateIdCardRequest | null> {
  const created = await apiFetch<DuplicateIdCardRequest>("/api/idcards/duplicate/", {
    method: "POST",
    json: input,
  });
  return checkout(
    created,
    (body) =>
      apiFetch<DuplicateIdCardRequest>(`/api/idcards/duplicate/${created.id}/verify/`, {
        method: "POST",
        json: body,
      }),
    description,
  );
}
