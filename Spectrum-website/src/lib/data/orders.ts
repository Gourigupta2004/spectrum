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

/**
 * Creates the order, opens Razorpay Checkout and verifies the payment.
 * Resolves with the paid order, or null if the buyer closed the payment window.
 */
export async function payForPhotos(input: OrderInput, description: string): Promise<Order | null> {
  const order = await createOrder(input);
  if (order.status === "paid" || order.status === "delivered") return order;
  if (order.mock) return verifyOrder(order.id, { mock: true });
  if (!order.razorpay) throw new Error("Payment is not available right now.");

  await loadCheckout();
  const razorpay = order.razorpay;
  return new Promise<Order | null>((resolve, reject) => {
    const checkout = new window.Razorpay!({
      key: razorpay.keyId,
      order_id: razorpay.orderId,
      amount: order.amountPaise,
      currency: order.currency,
      name: "Spectrum",
      description,
      prefill: order.prefill,
      theme: { color: "#7C4DE0" },
      handler: (response) => {
        verifyOrder(order.id, {
          razorpayOrderId: response.razorpay_order_id,
          razorpayPaymentId: response.razorpay_payment_id,
          razorpaySignature: response.razorpay_signature,
        }).then(resolve, reject);
      },
      modal: { ondismiss: () => resolve(null) },
    });
    checkout.on("payment.failed", () => reject(new Error("Payment failed")));
    checkout.open();
  });
}
