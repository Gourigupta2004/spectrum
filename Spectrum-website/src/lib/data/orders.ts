import { apiFetch, hasApi } from "../api";

export type DeliverVia = "whatsapp" | "email";

export type OrderInput = {
  eventSlug: string;
  photoIds: string[];
  videoIds: string[];
  bundle: boolean;
  name: string;
  phone: string;
  email: string;
  deliverVia: DeliverVia;
  idempotencyKey: string;
};

export type Order = {
  id: string;
  publicId: string;
  status: "created" | "paid" | "failed" | "delivered" | "refunded";
  amount: number;
  amountPaise: number;
  currency: string;
  deliverVia: DeliverVia;
  mock: boolean;
  razorpay: { keyId: string; orderId: string } | null;
  prefill: { name: string; email: string; contact: string };
  /** True once the payment is confirmed; the files arrive by WhatsApp/email. */
  paid: boolean;
};

export const createOrder = (input: OrderInput) =>
  apiFetch<Order>("/api/orders/", { method: "POST", json: input });

export const verifyOrder = (id: string, body: Record<string, unknown>) =>
  apiFetch<Order>(`/api/orders/${id}/verify/`, { method: "POST", json: body });

type RazorpayResponse = {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
};

type RazorpayOptions = {
  key: string;
  order_id: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  prefill: { name: string; email: string; contact: string };
  theme: { color: string };
  handler: (response: RazorpayResponse) => void;
  modal: { ondismiss: () => void };
};

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => {
      open: () => void;
      on: (event: string, cb: () => void) => void;
    };
  }
}

let checkoutScript: Promise<void> | null = null;

function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  checkoutScript ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      checkoutScript = null;
      reject(new Error("Could not load Razorpay"));
    };
    document.head.appendChild(script);
  });
  return checkoutScript;
}

/** What Checkout needs from anything paid through Razorpay: a photo order or an ID card request. */
export type Payable = {
  id: string;
  amountPaise: number;
  currency: string;
  mock: boolean;
  razorpay: { keyId: string; orderId: string } | null;
  prefill: { name: string; email: string; contact: string };
  paid: boolean;
};

/** One key per attempt, so a double click or retry never creates two orders. */
export const newIdempotencyKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

/**
 * Opens Razorpay Checkout for something the server has created, and verifies
 * the payment. Resolves with the paid result, or null if the buyer closed the
 * payment window.
 */
export async function checkout<T extends Payable>(
  created: T,
  verify: (body: Record<string, unknown>) => Promise<T>,
  description: string,
): Promise<T | null> {
  if (created.paid) return created;
  if (created.mock) return verify({ mock: true });
  if (!created.razorpay) throw new Error("Payment is not available right now.");

  await loadCheckout();
  const razorpay = created.razorpay;
  return new Promise<T | null>((resolve, reject) => {
    const rzp = new window.Razorpay!({
      key: razorpay.keyId,
      order_id: razorpay.orderId,
      amount: created.amountPaise,
      currency: created.currency,
      name: "Spectrum",
      description,
      prefill: created.prefill,
      theme: { color: "#7C4DE0" },
      handler: (response) => {
        verify({
          razorpayOrderId: response.razorpay_order_id,
          razorpayPaymentId: response.razorpay_payment_id,
          razorpaySignature: response.razorpay_signature,
        }).then(resolve, reject);
      },
      modal: { ondismiss: () => resolve(null) },
    });
    rzp.on("payment.failed", () => reject(new Error("Payment failed")));
    rzp.open();
  });
}

/**
 * Creates the order, opens Razorpay Checkout and verifies the payment.
 * Resolves with the paid order, or null if the buyer closed the payment window.
 */
export async function payForPhotos(input: OrderInput, description: string): Promise<Order | null> {
  const order = await createOrder(input);
  return checkout(order, (body) => verifyOrder(order.id, body), description);
}
