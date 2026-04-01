/**
 * Payment processing service with retry logic and partial failure handling.
 * Review this code for bugs, error handling gaps, and correctness problems.
 */

interface PaymentRequest {
  orderId: string;
  userId: string;
  amount: number;
  currency: string;
  items: { sku: string; qty: number; price: number }[];
}

interface PaymentResult {
  transactionId: string;
  status: "success" | "failed" | "pending";
  error?: string;
}

class PaymentService {
  private gateway: PaymentGateway;
  private db: Database;
  private inventory: InventoryService;
  private notifications: NotificationService;

  constructor(deps: {
    gateway: PaymentGateway;
    db: Database;
    inventory: InventoryService;
    notifications: NotificationService;
  }) {
    this.gateway = deps.gateway;
    this.db = deps.db;
    this.inventory = deps.inventory;
    this.notifications = deps.notifications;
  }

  async processPayment(req: PaymentRequest): Promise<PaymentResult> {
    // Validate amount
    const calculatedTotal = req.items.reduce((sum, item) => sum + item.price * item.qty, 0);
    if (calculatedTotal !== req.amount) {
      throw new Error("Amount mismatch");
    }

    // Reserve inventory
    for (const item of req.items) {
      await this.inventory.reserve(item.sku, item.qty);
    }

    // Create order record
    await this.db.insert("orders", {
      id: req.orderId,
      userId: req.userId,
      amount: req.amount,
      currency: req.currency,
      status: "pending",
      createdAt: new Date(),
    });

    // Charge the payment
    let result: PaymentResult;
    try {
      result = await this.retryWithBackoff(
        () => this.gateway.charge(req.userId, req.amount, req.currency),
        3
      );
    } catch (err) {
      // Payment failed — update order status
      await this.db.update("orders", req.orderId, { status: "failed" });
      throw err;
    }

    // Update order with transaction
    await this.db.update("orders", req.orderId, {
      status: result.status,
      transactionId: result.transactionId,
    });

    // Send confirmation
    this.notifications.send(req.userId, {
      type: "payment_confirmation",
      orderId: req.orderId,
      amount: req.amount,
    });

    return result;
  }

  async refund(orderId: string, reason: string): Promise<void> {
    const order = await this.db.get("orders", orderId);
    if (!order) throw new Error("Order not found");
    if (order.status !== "success") throw new Error("Cannot refund non-successful order");

    const refundResult = await this.gateway.refund(order.transactionId, order.amount);

    await this.db.update("orders", orderId, {
      status: "refunded",
      refundReason: reason,
      refundedAt: new Date(),
    });

    // Release inventory
    const items = await this.db.query("order_items", { orderId });
    for (const item of items) {
      this.inventory.release(item.sku, item.qty);
    }

    this.notifications.send(order.userId, {
      type: "refund_confirmation",
      orderId,
      amount: order.amount,
    });
  }

  async retryWithBackoff<T>(
    fn: () => Promise<T>,
    maxRetries: number,
    baseDelay = 1000
  ): Promise<T> {
    let lastError: Error;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (err) {
        lastError = err as Error;
        if (attempt < maxRetries) {
          await this.sleep(baseDelay * Math.pow(2, attempt));
        }
      }
    }
    throw lastError!;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async batchProcess(requests: PaymentRequest[]): Promise<Map<string, PaymentResult>> {
    const results = new Map<string, PaymentResult>();

    const promises = requests.map(async (req) => {
      try {
        const result = await this.processPayment(req);
        results.set(req.orderId, result);
      } catch (err) {
        results.set(req.orderId, {
          transactionId: "",
          status: "failed",
          error: (err as Error).message,
        });
      }
    });

    await Promise.all(promises);
    return results;
  }
}

// Stub interfaces for type checking
interface PaymentGateway {
  charge(userId: string, amount: number, currency: string): Promise<PaymentResult>;
  refund(transactionId: string, amount: number): Promise<{ status: string }>;
}

interface Database {
  insert(table: string, record: any): Promise<void>;
  update(table: string, id: string, fields: any): Promise<void>;
  get(table: string, id: string): Promise<any>;
  query(table: string, filter: any): Promise<any[]>;
}

interface InventoryService {
  reserve(sku: string, qty: number): Promise<void>;
  release(sku: string, qty: number): Promise<void>;
}

interface NotificationService {
  send(userId: string, payload: any): void;
}
