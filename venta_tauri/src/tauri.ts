import { invoke } from "@tauri-apps/api/core";
import { getVersion as tauriGetVersion } from "@tauri-apps/api/app";
import {
  AuthBootstrapCreateRequest,
  AuthBootstrapStatusResponse,
  AuthSessionResponse,
  BackupFileInfo,
  BackupConfigResponse,
  BackupMaintenanceResponse,
  BackupStatusResponse,
  BackupVerifyResponse,
  CategoryAdminSummary,
  DeletedCategoryArchiveRow,
  CategoryDeleteResponse,
  CategorySummary,
  ComboAdminRow,
  ComboDeleteResponse,
  ComboPreviewResponse,
  CreateBackupResponse,
  CreateComboRequest,
  CreateCustomerRequest,
  CreateCategoryRequest,
  DashboardExecutiveResponse,
  LoginRequest,
  CreateProductRequest,
  CreateSaleRequest,
  CreateUserRequest,
  CreateSaleResponse,
  CustomerAccountSnapshotResponse,
  DashboardSnapshotResponse,
  CustomerSummary,
  InventoryMovementRow,
  FavoriteProductRow,
  PaymentMethod,
  ProductSummary,
  ProductAdminRow,
  QualityAuditResponse,
  QuickStockLookupResponse,
  QuickStockAddRequest,
  QuickStockAddResponse,
  ReverseSaleRequest,
  ReverseSaleResponse,
  ReverseStockMovementRequest,
  ReverseStockMovementResponse,
  RestoreDeletedCategoryResponse,
  RestoreBackupResponse,
  RegisterInventoryMovementRequest,
  RegisterInventoryMovementResponse,
  SaleItemInput,
  SalesReportResponse,
  SaleTicketResponse,
  SetFavoriteProductResponse,
  TicketPrintRow,
  TicketSettingsResponse,
  UpdateBackupConfigRequest,
  UpdateComboRequest,
  UpdateCustomerRequest,
  UpdateTicketSettingsRequest,
  RegisterCustomerPaymentRequest,
  RegisterCustomerPaymentResponse,
  StockMovementSummary,
  UpdateUserRequest,
  UserDeleteResponse,
  UserRow,
  UpdateCategoryRequest,
  UpdateProductRequest,
} from "./types";

function hasTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export const APP_FALLBACK_VERSION = "1.0.14";

function stringifyInvokeError(error: unknown): string {
  if (typeof error === "string") {
    return error;
  }
  if (error && typeof error === "object" && "message" in error) {
    const maybeMessage = (error as { message?: unknown }).message;
    if (typeof maybeMessage === "string") {
      return maybeMessage;
    }
  }
  return "Error inesperado al ejecutar comando";
}

async function invokeStrict<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  if (!hasTauriRuntime()) {
    throw new Error("Esta vista requiere ejecutar la app en runtime Tauri.");
  }

  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw new Error(stringifyInvokeError(error));
  }
}

export async function healthCheck(): Promise<string> {
  try {
    return await invoke<string>("health_check");
  } catch {
    return "preview-web";
  }
}

export async function getAppVersion(): Promise<string> {
  if (!hasTauriRuntime()) {
    return APP_FALLBACK_VERSION;
  }
  try {
    return await tauriGetVersion();
  } catch {
    return APP_FALLBACK_VERSION;
  }
}

export function listPaymentMethods(): Promise<PaymentMethod[]> {
  return invokeStrict<PaymentMethod[]>("payment_methods");
}

export function authSession(): Promise<AuthSessionResponse> {
  return invokeStrict<AuthSessionResponse>("auth_session");
}

export function authBootstrapStatus(): Promise<AuthBootstrapStatusResponse> {
  return invokeStrict<AuthBootstrapStatusResponse>("auth_bootstrap_status");
}

export function authBootstrapCreateAdmin(
  payload: AuthBootstrapCreateRequest,
): Promise<AuthSessionResponse> {
  return invokeStrict<AuthSessionResponse>("auth_bootstrap_create_admin", { payload });
}

export function authLogin(payload: LoginRequest): Promise<AuthSessionResponse> {
  return invokeStrict<AuthSessionResponse>("auth_login", { payload });
}

export function authLogout(): Promise<AuthSessionResponse> {
  return invokeStrict<AuthSessionResponse>("auth_logout");
}

export function listUsers(includeInactive = true): Promise<UserRow[]> {
  return invokeStrict<UserRow[]>("list_users", { includeInactive });
}

export function createUser(payload: CreateUserRequest): Promise<UserRow> {
  return invokeStrict<UserRow>("create_user", { payload });
}

export function updateUser(payload: UpdateUserRequest): Promise<UserRow> {
  return invokeStrict<UserRow>("update_user", { payload });
}

export function deleteUser(userId: number): Promise<UserDeleteResponse> {
  return invokeStrict<UserDeleteResponse>("delete_user", { userId });
}

export function backupStatus(): Promise<BackupStatusResponse> {
  return invokeStrict<BackupStatusResponse>("backup_status");
}

export function backupConfig(): Promise<BackupConfigResponse> {
  return invokeStrict<BackupConfigResponse>("backup_config");
}

export function updateBackupConfig(payload: UpdateBackupConfigRequest): Promise<BackupConfigResponse> {
  return invokeStrict<BackupConfigResponse>("update_backup_config", { payload });
}

export function listBackupFiles(limit = 120): Promise<BackupFileInfo[]> {
  return invokeStrict<BackupFileInfo[]>("list_backup_files", { limit });
}

export function createBackup(targetPath?: string): Promise<CreateBackupResponse> {
  return invokeStrict<CreateBackupResponse>("create_backup", { targetPath });
}

export function restoreBackup(sourcePath: string): Promise<RestoreBackupResponse> {
  return invokeStrict<RestoreBackupResponse>("restore_backup", { sourcePath });
}

export function runBackupMaintenance(force = false): Promise<BackupMaintenanceResponse> {
  return invokeStrict<BackupMaintenanceResponse>("run_backup_maintenance", { force });
}

export function verifyBackupFile(path: string): Promise<BackupVerifyResponse> {
  return invokeStrict<BackupVerifyResponse>("verify_backup_file", { path });
}

export function searchProducts(term?: string, limit = 25): Promise<ProductSummary[]> {
  return invokeStrict<ProductSummary[]>("search_products", { term, limit });
}

export function getProductByBarcode(barcode: string): Promise<ProductSummary | null> {
  return invokeStrict<ProductSummary | null>("get_product_by_barcode", { barcode });
}

export function listFavoriteProducts(limit = 18): Promise<FavoriteProductRow[]> {
  return invokeStrict<FavoriteProductRow[]>("list_favorite_products", { limit });
}

export function setProductFavorite(
  productId: number,
  favorite: boolean,
): Promise<SetFavoriteProductResponse> {
  return invokeStrict<SetFavoriteProductResponse>("set_product_favorite", {
    productId,
    favorite,
  });
}

export function listCustomers(search?: string, limit = 120): Promise<CustomerSummary[]> {
  return invokeStrict<CustomerSummary[]>("list_customers", { search, limit });
}

export function createCustomer(payload: CreateCustomerRequest): Promise<CustomerSummary> {
  return invokeStrict<CustomerSummary>("create_customer", { payload });
}

export function updateCustomer(payload: UpdateCustomerRequest): Promise<CustomerSummary> {
  return invokeStrict<CustomerSummary>("update_customer", { payload });
}

export function customerAccountSnapshot(
  customerId: number,
  salesLimit = 30,
  paymentsLimit = 40,
): Promise<CustomerAccountSnapshotResponse> {
  return invokeStrict<CustomerAccountSnapshotResponse>("customer_account_snapshot", {
    customerId,
    salesLimit,
    paymentsLimit,
  });
}

export function registerCustomerPayment(
  payload: RegisterCustomerPaymentRequest,
): Promise<RegisterCustomerPaymentResponse> {
  return invokeStrict<RegisterCustomerPaymentResponse>("register_customer_payment", {
    payload,
  });
}

export function listCategories(): Promise<CategorySummary[]> {
  return invokeStrict<CategorySummary[]>("list_categories");
}

export function listCategoriesAdmin(): Promise<CategoryAdminSummary[]> {
  return invokeStrict<CategoryAdminSummary[]>("list_categories_admin");
}

export function createCategory(payload: CreateCategoryRequest): Promise<CategoryAdminSummary> {
  return invokeStrict<CategoryAdminSummary>("create_category", { payload });
}

export function updateCategory(payload: UpdateCategoryRequest): Promise<CategoryAdminSummary> {
  return invokeStrict<CategoryAdminSummary>("update_category", { payload });
}

export function deleteCategory(categoryId: number): Promise<CategoryDeleteResponse> {
  return invokeStrict<CategoryDeleteResponse>("delete_category", { categoryId });
}

export function listDeletedCategories(): Promise<DeletedCategoryArchiveRow[]> {
  return invokeStrict<DeletedCategoryArchiveRow[]>("list_deleted_categories");
}

export function restoreDeletedCategory(archiveId: number): Promise<RestoreDeletedCategoryResponse> {
  return invokeStrict<RestoreDeletedCategoryResponse>("restore_deleted_category", {
    payload: { archiveId },
  });
}

export function listCombosAdmin(): Promise<ComboAdminRow[]> {
  return invokeStrict<ComboAdminRow[]>("list_combos_admin");
}

export function createCombo(payload: CreateComboRequest): Promise<ComboAdminRow> {
  return invokeStrict<ComboAdminRow>("create_combo", { payload });
}

export function updateCombo(payload: UpdateComboRequest): Promise<ComboAdminRow> {
  return invokeStrict<ComboAdminRow>("update_combo", { payload });
}

export function deleteCombo(comboId: number): Promise<ComboDeleteResponse> {
  return invokeStrict<ComboDeleteResponse>("delete_combo", { comboId });
}

export function listProductsAdmin(
  search?: string,
  categoryId?: number,
  includeInactive = false,
  limit = 200,
): Promise<ProductAdminRow[]> {
  return invokeStrict<ProductAdminRow[]>("list_products_admin", {
    search,
    categoryId,
    includeInactive,
    limit,
  });
}

export function createProduct(payload: CreateProductRequest): Promise<ProductSummary> {
  return invokeStrict<ProductSummary>("create_product", { payload });
}

export function updateProduct(payload: UpdateProductRequest): Promise<ProductAdminRow> {
  return invokeStrict<ProductAdminRow>("update_product", { payload });
}

export function inventoryListMovements(
  search?: string,
  movementType?: string,
  limit = 260,
): Promise<InventoryMovementRow[]> {
  return invokeStrict<InventoryMovementRow[]>("inventory_list_movements", {
    search,
    movementType,
    limit,
  });
}

export function registerInventoryMovement(
  payload: RegisterInventoryMovementRequest,
): Promise<RegisterInventoryMovementResponse> {
  return invokeStrict<RegisterInventoryMovementResponse>("register_inventory_movement", {
    payload,
  });
}

export function reverseStockMovement(
  payload: ReverseStockMovementRequest,
): Promise<ReverseStockMovementResponse> {
  return invokeStrict<ReverseStockMovementResponse>("reverse_stock_movement", { payload });
}

export function listRecentStockMovements(limit = 40): Promise<StockMovementSummary[]> {
  return invokeStrict<StockMovementSummary[]>("list_recent_stock_movements", { limit });
}

export function quickStockLookupByBarcode(barcode: string): Promise<QuickStockLookupResponse> {
  return invokeStrict<QuickStockLookupResponse>("quick_stock_lookup_by_barcode", { barcode });
}

export function quickStockAddByBarcode(payload: QuickStockAddRequest): Promise<QuickStockAddResponse> {
  return invokeStrict<QuickStockAddResponse>("quick_stock_add_by_barcode", { payload });
}

export function previewSaleCombos(
  items: SaleItemInput[],
  selectedComboIds?: number[],
): Promise<ComboPreviewResponse> {
  return invokeStrict<ComboPreviewResponse>("preview_sale_combos", {
    payload: {
      items,
      selectedComboIds,
    },
  });
}

export function createSale(payload: CreateSaleRequest): Promise<CreateSaleResponse> {
  return invokeStrict<CreateSaleResponse>("create_sale", { payload });
}

export function reverseSale(payload: ReverseSaleRequest): Promise<ReverseSaleResponse> {
  return invokeStrict<ReverseSaleResponse>("reverse_sale", { payload });
}

export function dashboardSnapshot(month?: string): Promise<DashboardSnapshotResponse> {
  return invokeStrict<DashboardSnapshotResponse>("dashboard_snapshot", { month });
}

export function dashboardExecutive(month?: string): Promise<DashboardExecutiveResponse> {
  return invokeStrict<DashboardExecutiveResponse>("dashboard_executive", { month });
}

export function salesReport(
  fromDate: string,
  toDate: string,
  paymentMethod?: string,
  salesLimit = 200,
  productsLimit = 120,
): Promise<SalesReportResponse> {
  return invokeStrict<SalesReportResponse>("sales_report", {
    fromDate,
    toDate,
    paymentMethod,
    salesLimit,
    productsLimit,
  });
}

export function ticketSettings(): Promise<TicketSettingsResponse> {
  return invokeStrict<TicketSettingsResponse>("ticket_settings");
}

export function updateTicketSettings(payload: UpdateTicketSettingsRequest): Promise<TicketSettingsResponse> {
  return invokeStrict<TicketSettingsResponse>("update_ticket_settings", { payload });
}

export function generateSaleTicket(saleId: number, copyType = "reimpresion"): Promise<SaleTicketResponse> {
  return invokeStrict<SaleTicketResponse>("generate_sale_ticket", {
    saleId,
    copyType,
  });
}

export function listTicketPrints(limit = 120): Promise<TicketPrintRow[]> {
  return invokeStrict<TicketPrintRow[]>("list_ticket_prints", { limit });
}

export function qualityAudit(): Promise<QualityAuditResponse> {
  return invokeStrict<QualityAuditResponse>("quality_audit");
}

