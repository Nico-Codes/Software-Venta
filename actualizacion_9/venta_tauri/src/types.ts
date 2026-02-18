export type PrimarySection = "quick-sale" | "quick-stock";

export type UtilitySection =
  | "dashboard"
  | "products"
  | "categories"
  | "inventory"
  | "reports"
  | "customers"
  | "users"
  | "backup"
  | "tickets"
  | "quality";

export type ViewKey = PrimarySection | UtilitySection;

export type PaymentMethod = "Efectivo" | "Credito" | "Debito" | "Transferencia" | "Deuda";

export type UserRole = "admin" | "seller";

export type SessionUser = {
  id: number;
  username: string;
  displayName: string;
  role: UserRole | string;
};

export type AuthSessionResponse = {
  authenticated: boolean;
  user: SessionUser | null;
};

export type AuthBootstrapStatusResponse = {
  needsSetup: boolean;
  usersCount: number;
};

export type LoginRequest = {
  username: string;
  password: string;
};

export type AuthBootstrapCreateRequest = {
  username: string;
  displayName: string;
  password: string;
};

export type UserRow = {
  id: number;
  username: string;
  displayName: string;
  role: UserRole | string;
  active: boolean;
  createdAt: string;
  updatedAt: string;
};

export type CreateUserRequest = {
  username: string;
  displayName: string;
  role: UserRole;
  password: string;
  active: boolean;
};

export type UpdateUserRequest = {
  id: number;
  username: string;
  displayName: string;
  role: UserRole;
  password?: string;
  active: boolean;
};

export type UserDeleteResponse = {
  id: number;
};

export type BackupStatusResponse = {
  dbPath: string;
  backupDir: string;
  dbExists: boolean;
  dbSizeBytes: number;
  dbModifiedAt: string | null;
};

export type BackupConfigResponse = {
  autoEnabled: boolean;
  intervalHours: number;
  retentionCount: number;
  lastRunAt: string | null;
};

export type UpdateBackupConfigRequest = {
  autoEnabled: boolean;
  intervalHours: number;
  retentionCount: number;
};

export type BackupFileInfo = {
  path: string;
  fileName: string;
  sizeBytes: number;
  modifiedAt: string | null;
};

export type CreateBackupResponse = {
  backupPath: string;
  sizeBytes: number;
};

export type RestoreBackupResponse = {
  dbPath: string;
  message: string;
  preRestoreBackupPath: string | null;
};

export type BackupMaintenanceResponse = {
  executedAt: string;
  createdBackupPath: string | null;
  deletedFiles: string[];
  skippedReason: string | null;
};

export type BackupVerifyResponse = {
  path: string;
  ok: boolean;
  message: string;
};

export type ProductSummary = {
  id: number;
  name: string;
  barcode: string | null;
  salePrice: number;
  stock: number;
};

export type CustomerSummary = {
  id: number;
  name: string;
  debtTotal: number;
  alertLimit: number;
  overLimit: boolean;
  overdueSalesCount: number;
  overdueTotal: number;
  maxDaysOverdue: number;
};

export type CreateCustomerRequest = {
  name: string;
  phone?: string;
  email?: string;
  alertLimit?: number;
  notes?: string;
};

export type CustomerAccountInfo = {
  id: number;
  name: string;
  phone: string | null;
  email: string | null;
  alertLimit: number;
  notes: string | null;
  debtTotal: number;
  overLimit: boolean;
  overdueSalesCount: number;
  overdueTotal: number;
};

export type CustomerSaleItem = {
  saleId: number;
  soldAt: string;
  total: number;
  paidAmount: number;
  balanceDue: number;
  dueDate: string | null;
  overdueDays: number;
  paymentMethod: string;
  status: string;
};

export type CustomerPaymentItem = {
  id: number;
  saleId: number | null;
  paidAt: string;
  amount: number;
  paymentMethod: string;
  note: string | null;
};

export type CustomerAccountSnapshotResponse = {
  customer: CustomerAccountInfo;
  debtSales: CustomerSaleItem[];
  recentSales: CustomerSaleItem[];
  recentPayments: CustomerPaymentItem[];
};

export type RegisterCustomerPaymentRequest = {
  customerId: number;
  amount: number;
  paymentMethod: PaymentMethod;
  note?: string;
};

export type RegisterCustomerPaymentResponse = {
  customerId: number;
  appliedTotal: number;
  debtTotalBefore: number;
  debtTotalAfter: number;
  affectedSales: number;
};

export type UpdateCustomerRequest = {
  customerId: number;
  alertLimit?: number;
  notes?: string;
  active?: boolean;
};

export type CategorySummary = {
  id: number;
  name: string;
  marginPercent: number;
};

export type CategoryAdminSummary = {
  id: number;
  name: string;
  marginPercent: number;
  productCount: number;
};

export type CreateCategoryRequest = {
  name: string;
  marginPercent: number;
};

export type UpdateCategoryRequest = {
  id: number;
  name: string;
  marginPercent: number;
};

export type CategoryDeleteResponse = {
  id: number;
};

export type ProductAdminRow = {
  id: number;
  name: string;
  barcode: string | null;
  categoryId: number;
  categoryName: string;
  cost: number;
  salePrice: number;
  autoPrice: boolean;
  stock: number;
  minStock: number;
  active: boolean;
};

export type UpdateProductRequest = {
  id: number;
  name: string;
  barcode: string;
  categoryId: number;
  cost: number;
  salePrice: number;
  stock: number;
  minStock: number;
  autoPrice: boolean;
  active: boolean;
};

export type StockMovementSummary = {
  id: number;
  createdAt: string;
  movementType: string;
  quantity: number;
  stockBefore: number;
  stockAfter: number;
  productName: string;
  barcode: string | null;
};

export type InventoryMovementType = "manual_in" | "manual_out" | "adjustment" | "sale";

export type InventoryMovementRow = {
  id: number;
  createdAt: string;
  movementType: InventoryMovementType | string;
  quantity: number;
  stockBefore: number;
  stockAfter: number;
  productId: number;
  productName: string;
  barcode: string | null;
  note: string | null;
};

export type RegisterInventoryMovementRequest = {
  productId: number;
  movementType: "manual_in" | "manual_out" | "adjustment";
  quantity?: number;
  stockTarget?: number;
  note?: string;
};

export type RegisterInventoryMovementResponse = {
  message: string;
  product: ProductSummary;
  movement: InventoryMovementRow;
};

export type SaleItemInput = {
  productId: number;
  quantity: number;
};

export type CreateSaleRequest = {
  items: SaleItemInput[];
  paymentMethod: PaymentMethod;
  notes?: string;
  customerId?: number;
  paidAmount?: number;
  initialPaymentMethod?: PaymentMethod;
  dueDate?: string;
};

export type CreateSaleResponse = {
  saleId: number;
  soldAt: string;
  total: number;
  paymentMethod: PaymentMethod;
  saleType: "cash" | "credit";
  customerId?: number;
  paidAmount: number;
  balanceDue: number;
  dueDate?: string;
  status: "paid" | "partial" | "credit";
  initialPaymentMethod?: PaymentMethod;
};

export type QuickStockAddRequest = {
  barcode: string;
  quantity: number;
  note?: string;
};

export type QuickStockAddResponse = {
  found: boolean;
  message: string;
  product?: ProductSummary;
  movementId?: number;
};

export type CreateProductRequest = {
  name: string;
  barcode: string;
  categoryId: number;
  cost: number;
  salePrice: number;
  stock: number;
  minStock: number;
  autoPrice: boolean;
};

export type DashboardSummary = {
  salesCount: number;
  grossTotal: number;
  paidTotal: number;
  dueTotal: number;
  estimatedProfit: number;
};

export type PaymentBreakdownItem = {
  paymentMethod: PaymentMethod;
  total: number;
};

export type ProductRankingItem = {
  productName: string;
  quantity: number;
  revenue: number;
};

export type LowStockAlertItem = {
  id: number;
  name: string;
  barcode: string | null;
  stock: number;
  minStock: number;
  shortage: number;
};

export type DailySalesPoint = {
  soldDay: string;
  total: number;
};

export type DashboardSnapshotResponse = {
  month: string;
  summary: DashboardSummary;
  paymentBreakdown: PaymentBreakdownItem[];
  topProducts: ProductRankingItem[];
  lowProducts: ProductRankingItem[];
  lowStockAlerts: LowStockAlertItem[];
  dailySales: DailySalesPoint[];
};

export type DashboardCompareBlock = {
  month: string;
  grossTotal: number;
  paidTotal: number;
  dueTotal: number;
  estimatedProfit: number;
  salesCount: number;
  avgTicket: number;
};

export type HourSalesPoint = {
  hour: number;
  total: number;
  salesCount: number;
};

export type CategoryProfitPoint = {
  categoryName: string;
  revenue: number;
  profit: number;
};

export type DashboardExecutiveResponse = {
  current: DashboardCompareBlock;
  previous: DashboardCompareBlock;
  grossDeltaPercent: number;
  profitDeltaPercent: number;
  avgTicketDeltaPercent: number;
  peakHours: HourSalesPoint[];
  categoryProfit: CategoryProfitPoint[];
};

export type ReportSummary = {
  salesCount: number;
  grossTotal: number;
  paidTotal: number;
  dueTotal: number;
  estimatedProfit: number;
  avgTicket: number;
};

export type ReportSaleRow = {
  saleId: number;
  soldAt: string;
  customerName: string | null;
  paymentMethod: string;
  total: number;
  paidAmount: number;
  balanceDue: number;
  status: string;
};

export type ReportProductRow = {
  productName: string;
  quantity: number;
  revenue: number;
  costTotal: number;
  profit: number;
};

export type SalesReportResponse = {
  fromDate: string;
  toDate: string;
  paymentMethod: string | null;
  summary: ReportSummary;
  paymentBreakdown: PaymentBreakdownItem[];
  sales: ReportSaleRow[];
  products: ReportProductRow[];
};

export type FavoriteProductRow = {
  productId: number;
  name: string;
  barcode: string | null;
  salePrice: number;
  stock: number;
};

export type SetFavoriteProductResponse = {
  productId: number;
  favorite: boolean;
};

export type TicketSettingsResponse = {
  storeName: string;
  taxId: string;
  address: string;
  phone: string;
  headerText: string;
  footerText: string;
  paperWidthMm: number;
  logoPath: string;
  showLogo: boolean;
};

export type UpdateTicketSettingsRequest = {
  storeName?: string;
  taxId?: string;
  address?: string;
  phone?: string;
  headerText?: string;
  footerText?: string;
  paperWidthMm?: number;
  logoPath?: string;
  showLogo?: boolean;
};

export type SaleTicketItem = {
  productName: string;
  quantity: number;
  unitPrice: number;
  subtotal: number;
};

export type SaleTicketResponse = {
  saleId: number;
  printedAt: string;
  paperWidthMm: number;
  title: string;
  bodyText: string;
  total: number;
  paidAmount: number;
  balanceDue: number;
  paymentMethod: string;
  customerName: string | null;
  copyType: string;
  items: SaleTicketItem[];
};

export type TicketPrintRow = {
  id: number;
  saleId: number;
  printedAt: string;
  copyType: string;
  total: number;
  paidAmount: number;
  balanceDue: number;
  paymentMethod: string;
  customerName: string | null;
};

export type QualityIssue = {
  code: string;
  severity: string;
  detail: string;
};

export type QualityAuditResponse = {
  checkedAt: string;
  issues: QualityIssue[];
  productsCount: number;
  salesCount: number;
  customersCount: number;
};
