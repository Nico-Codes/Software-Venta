#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use chrono::{DateTime, Datelike, Duration, Local, NaiveDate, NaiveDateTime};
use pbkdf2::pbkdf2_hmac;
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use tauri::{AppHandle, Manager};

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ProductSummary {
    id: i64,
    name: String,
    barcode: Option<String>,
    sale_price: f64,
    stock: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CustomerSummary {
    id: i64,
    name: String,
    debt_total: f64,
    alert_limit: f64,
    over_limit: bool,
    overdue_sales_count: i64,
    overdue_total: f64,
    max_days_overdue: i64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateCustomerRequest {
    name: String,
    phone: Option<String>,
    email: Option<String>,
    alert_limit: Option<f64>,
    notes: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CustomerAccountInfo {
    id: i64,
    name: String,
    phone: Option<String>,
    email: Option<String>,
    alert_limit: f64,
    notes: Option<String>,
    debt_total: f64,
    over_limit: bool,
    overdue_sales_count: i64,
    overdue_total: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CustomerSaleItem {
    sale_id: i64,
    sold_at: String,
    total: f64,
    paid_amount: f64,
    balance_due: f64,
    due_date: Option<String>,
    overdue_days: i64,
    payment_method: String,
    status: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CustomerPaymentItem {
    id: i64,
    sale_id: Option<i64>,
    paid_at: String,
    amount: f64,
    payment_method: String,
    note: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CustomerAccountSnapshotResponse {
    customer: CustomerAccountInfo,
    debt_sales: Vec<CustomerSaleItem>,
    recent_sales: Vec<CustomerSaleItem>,
    recent_payments: Vec<CustomerPaymentItem>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RegisterCustomerPaymentRequest {
    customer_id: i64,
    amount: f64,
    payment_method: String,
    note: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RegisterCustomerPaymentResponse {
    customer_id: i64,
    applied_total: f64,
    debt_total_before: f64,
    debt_total_after: f64,
    affected_sales: i64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CategorySummary {
    id: i64,
    name: String,
    margin_percent: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CategoryAdminSummary {
    id: i64,
    name: String,
    margin_percent: f64,
    product_count: i64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateCategoryRequest {
    name: String,
    margin_percent: f64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdateCategoryRequest {
    id: i64,
    name: String,
    margin_percent: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CategoryDeleteResponse {
    id: i64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DeletedCategoryArchiveRow {
    archive_id: i64,
    original_category_id: i64,
    name: String,
    margin_percent: f64,
    deleted_at: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RestoreDeletedCategoryRequest {
    archive_id: i64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RestoreDeletedCategoryResponse {
    archive_id: i64,
    category: CategoryAdminSummary,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ProductAdminRow {
    id: i64,
    name: String,
    barcode: Option<String>,
    category_id: i64,
    category_name: String,
    cost: f64,
    sale_price: f64,
    auto_price: bool,
    stock: f64,
    min_stock: f64,
    active: bool,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdateProductRequest {
    id: i64,
    name: String,
    barcode: String,
    category_id: i64,
    cost: f64,
    sale_price: f64,
    stock: f64,
    min_stock: f64,
    auto_price: bool,
    active: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct StockMovementSummary {
    id: i64,
    created_at: String,
    movement_type: String,
    quantity: f64,
    stock_before: f64,
    stock_after: f64,
    product_name: String,
    barcode: Option<String>,
    reference_type: Option<String>,
    reference_id: Option<i64>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct InventoryMovementRow {
    id: i64,
    created_at: String,
    movement_type: String,
    quantity: f64,
    stock_before: f64,
    stock_after: f64,
    product_id: i64,
    product_name: String,
    barcode: Option<String>,
    note: Option<String>,
    reference_type: Option<String>,
    reference_id: Option<i64>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RegisterInventoryMovementRequest {
    product_id: i64,
    movement_type: String,
    quantity: Option<f64>,
    stock_target: Option<f64>,
    note: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RegisterInventoryMovementResponse {
    message: String,
    product: ProductSummary,
    movement: InventoryMovementRow,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ReverseStockMovementRequest {
    movement_id: i64,
    reason: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ReverseStockMovementResponse {
    movement_id: i64,
    reversal_movement_id: i64,
    reversed_at: String,
    product: ProductSummary,
    quantity_reverted: f64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct SaleItemInput {
    product_id: i64,
    quantity: f64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateSaleRequest {
    items: Vec<SaleItemInput>,
    payment_method: String,
    notes: Option<String>,
    customer_id: Option<i64>,
    paid_amount: Option<f64>,
    initial_payment_method: Option<String>,
    due_date: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CreateSaleResponse {
    sale_id: i64,
    sold_at: String,
    total: f64,
    payment_method: String,
    sale_type: String,
    customer_id: Option<i64>,
    paid_amount: f64,
    balance_due: f64,
    due_date: Option<String>,
    status: String,
    initial_payment_method: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ReverseSaleRequest {
    sale_id: i64,
    reason: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ReverseSaleResponse {
    sale_id: i64,
    reversed_at: String,
    restored_items: i64,
    restored_units: f64,
    removed_payments: i64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct QuickStockLookupProduct {
    id: i64,
    name: String,
    barcode: Option<String>,
    stock: f64,
    cost: f64,
    sale_price: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct QuickStockLookupResponse {
    found: bool,
    message: String,
    product: Option<QuickStockLookupProduct>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct QuickStockAddRequest {
    barcode: String,
    quantity: f64,
    unit_cost: Option<f64>,
    note: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct QuickStockAddResponse {
    found: bool,
    message: String,
    product: Option<ProductSummary>,
    movement_id: Option<i64>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateProductRequest {
    name: String,
    barcode: String,
    category_id: i64,
    cost: f64,
    sale_price: f64,
    stock: f64,
    min_stock: f64,
    auto_price: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DashboardSummary {
    sales_count: i64,
    gross_total: f64,
    paid_total: f64,
    due_total: f64,
    estimated_profit: f64,
    internal_consumption_total: f64,
    internal_operations_count: i64,
    net_profit_after_internal: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct PaymentBreakdownItem {
    payment_method: String,
    total: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ProductRankingItem {
    product_name: String,
    quantity: f64,
    revenue: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct LowStockAlertItem {
    id: i64,
    name: String,
    barcode: Option<String>,
    stock: f64,
    min_stock: f64,
    shortage: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DailySalesPoint {
    sold_day: String,
    total: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DashboardSnapshotResponse {
    month: String,
    summary: DashboardSummary,
    payment_breakdown: Vec<PaymentBreakdownItem>,
    top_products: Vec<ProductRankingItem>,
    low_products: Vec<ProductRankingItem>,
    low_stock_alerts: Vec<LowStockAlertItem>,
    daily_sales: Vec<DailySalesPoint>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ReportSummary {
    sales_count: i64,
    gross_total: f64,
    paid_total: f64,
    due_total: f64,
    estimated_profit: f64,
    internal_consumption_total: f64,
    internal_operations_count: i64,
    net_profit_after_internal: f64,
    avg_ticket: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ReportSaleRow {
    sale_id: i64,
    sold_at: String,
    customer_name: Option<String>,
    payment_method: String,
    total: f64,
    paid_amount: f64,
    balance_due: f64,
    status: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ReportProductRow {
    product_name: String,
    quantity: f64,
    revenue: f64,
    cost_total: f64,
    profit: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SalesReportResponse {
    from_date: String,
    to_date: String,
    payment_method: Option<String>,
    summary: ReportSummary,
    payment_breakdown: Vec<PaymentBreakdownItem>,
    sales: Vec<ReportSaleRow>,
    products: Vec<ReportProductRow>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct UserRow {
    id: i64,
    username: String,
    display_name: String,
    role: String,
    active: bool,
    created_at: String,
    updated_at: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateUserRequest {
    username: String,
    display_name: String,
    role: String,
    password: String,
    active: bool,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdateUserRequest {
    id: i64,
    username: String,
    display_name: String,
    role: String,
    password: Option<String>,
    active: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct UserDeleteResponse {
    id: i64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct LoginRequest {
    username: String,
    password: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct AuthBootstrapStatusResponse {
    needs_setup: bool,
    users_count: i64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AuthBootstrapCreateRequest {
    username: String,
    display_name: String,
    password: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SessionUser {
    id: i64,
    username: String,
    display_name: String,
    role: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct AuthSessionResponse {
    authenticated: bool,
    user: Option<SessionUser>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct BackupStatusResponse {
    db_path: String,
    backup_dir: String,
    db_exists: bool,
    db_size_bytes: i64,
    db_modified_at: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct BackupFileInfo {
    path: String,
    file_name: String,
    size_bytes: i64,
    modified_at: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CreateBackupResponse {
    backup_path: String,
    size_bytes: i64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RestoreBackupResponse {
    db_path: String,
    message: String,
    pre_restore_backup_path: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdateCustomerRequest {
    customer_id: i64,
    alert_limit: Option<f64>,
    notes: Option<String>,
    active: Option<bool>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DashboardCompareBlock {
    month: String,
    gross_total: f64,
    paid_total: f64,
    due_total: f64,
    estimated_profit: f64,
    internal_consumption_total: f64,
    internal_operations_count: i64,
    net_profit_after_internal: f64,
    sales_count: i64,
    avg_ticket: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct HourSalesPoint {
    hour: i64,
    total: f64,
    sales_count: i64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CategoryProfitPoint {
    category_name: String,
    revenue: f64,
    profit: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DashboardExecutiveResponse {
    current: DashboardCompareBlock,
    previous: DashboardCompareBlock,
    gross_delta_percent: f64,
    profit_delta_percent: f64,
    avg_ticket_delta_percent: f64,
    peak_hours: Vec<HourSalesPoint>,
    category_profit: Vec<CategoryProfitPoint>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct FavoriteProductRow {
    product_id: i64,
    name: String,
    barcode: Option<String>,
    sale_price: f64,
    stock: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SetFavoriteProductResponse {
    product_id: i64,
    favorite: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct TicketSettingsResponse {
    store_name: String,
    tax_id: String,
    address: String,
    phone: String,
    header_text: String,
    footer_text: String,
    paper_width_mm: i64,
    logo_path: String,
    show_logo: bool,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdateTicketSettingsRequest {
    store_name: Option<String>,
    tax_id: Option<String>,
    address: Option<String>,
    phone: Option<String>,
    header_text: Option<String>,
    footer_text: Option<String>,
    paper_width_mm: Option<i64>,
    logo_path: Option<String>,
    show_logo: Option<bool>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SaleTicketItem {
    product_name: String,
    quantity: f64,
    unit_price: f64,
    subtotal: f64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SaleTicketResponse {
    sale_id: i64,
    printed_at: String,
    paper_width_mm: i64,
    title: String,
    body_text: String,
    total: f64,
    paid_amount: f64,
    balance_due: f64,
    payment_method: String,
    customer_name: Option<String>,
    copy_type: String,
    items: Vec<SaleTicketItem>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct TicketPrintRow {
    id: i64,
    sale_id: i64,
    printed_at: String,
    copy_type: String,
    total: f64,
    paid_amount: f64,
    balance_due: f64,
    payment_method: String,
    customer_name: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct BackupConfigResponse {
    auto_enabled: bool,
    interval_hours: i64,
    retention_count: i64,
    last_run_at: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct UpdateBackupConfigRequest {
    auto_enabled: bool,
    interval_hours: i64,
    retention_count: i64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct BackupMaintenanceResponse {
    executed_at: String,
    created_backup_path: Option<String>,
    deleted_files: Vec<String>,
    skipped_reason: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct BackupVerifyResponse {
    path: String,
    ok: bool,
    message: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct QualityIssue {
    code: String,
    severity: String,
    detail: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct QualityAuditResponse {
    checked_at: String,
    issues: Vec<QualityIssue>,
    products_count: i64,
    sales_count: i64,
    customers_count: i64,
}

fn db_error(message: &str, err: impl std::fmt::Display) -> String {
    format!("{message}: {err}")
}

const SESSION_USER_ID_KEY: &str = "session_user_id";
const TICKET_STORE_NAME_KEY: &str = "ticket_store_name";
const TICKET_TAX_ID_KEY: &str = "ticket_tax_id";
const TICKET_ADDRESS_KEY: &str = "ticket_address";
const TICKET_PHONE_KEY: &str = "ticket_phone";
const TICKET_HEADER_KEY: &str = "ticket_header";
const TICKET_FOOTER_KEY: &str = "ticket_footer";
const TICKET_PAPER_WIDTH_KEY: &str = "ticket_paper_width_mm";
const TICKET_LOGO_PATH_KEY: &str = "ticket_logo_path";
const TICKET_SHOW_LOGO_KEY: &str = "ticket_show_logo";
const BACKUP_AUTO_ENABLED_KEY: &str = "backup_auto_enabled";
const BACKUP_INTERVAL_HOURS_KEY: &str = "backup_interval_hours";
const BACKUP_RETENTION_COUNT_KEY: &str = "backup_retention_count";
const BACKUP_LAST_RUN_AT_KEY: &str = "backup_last_run_at";
const DEFAULT_DUE_DAYS: i64 = 30;

fn table_has_column(
    conn: &Connection,
    table_name: &str,
    column_name: &str,
) -> Result<bool, String> {
    let pragma = format!("PRAGMA table_info({table_name})");
    let mut stmt = conn
        .prepare(&pragma)
        .map_err(|e| db_error("No se pudo consultar columnas de tabla", e))?;
    let rows = stmt
        .query_map([], |row| row.get::<_, String>(1))
        .map_err(|e| db_error("No se pudo listar columnas de tabla", e))?;

    for row in rows {
        let name = row.map_err(|e| db_error("No se pudo leer columna de tabla", e))?;
        if name == column_name {
            return Ok(true);
        }
    }
    Ok(false)
}

fn ensure_column_exists(
    conn: &Connection,
    table_name: &str,
    column_name: &str,
    column_def: &str,
    user_message: &str,
) -> Result<(), String> {
    if table_has_column(conn, table_name, column_name)? {
        return Ok(());
    }
    let sql = format!("ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}");
    conn.execute(&sql, [])
        .map_err(|e| db_error(user_message, e))?;
    Ok(())
}

fn round_integer(value: f64) -> f64 {
    if !value.is_finite() {
        return 0.0;
    }
    value.round()
}

fn round_non_negative_integer(value: f64) -> f64 {
    round_integer(value).max(0.0)
}

fn verify_legacy_password(password: &str, stored_hash: &str) -> bool {
    if password.trim().is_empty() || stored_hash.trim().is_empty() {
        return false;
    }

    let mut parts = stored_hash.trim().splitn(2, '$');
    let salt_hex = match parts.next() {
        Some(v) if !v.is_empty() => v,
        _ => return false,
    };
    let expected_hex = match parts.next() {
        Some(v) if !v.is_empty() => v.to_lowercase(),
        _ => return false,
    };

    let salt = match hex::decode(salt_hex) {
        Ok(bytes) if !bytes.is_empty() => bytes,
        _ => return false,
    };

    let mut out = [0_u8; 32];
    pbkdf2_hmac::<Sha256>(password.as_bytes(), &salt, 120_000, &mut out);
    let candidate_hex = hex::encode(out);
    candidate_hex == expected_hex
}

fn get_setting_text(conn: &Connection, key: &str, fallback: &str) -> String {
    conn.query_row(
        "SELECT value FROM settings WHERE key = ? LIMIT 1",
        params![key],
        |row| row.get::<_, String>(0),
    )
    .optional()
    .ok()
    .flatten()
    .unwrap_or_else(|| fallback.to_string())
}

fn get_setting_i64(conn: &Connection, key: &str, fallback: i64) -> i64 {
    get_setting_text(conn, key, &fallback.to_string())
        .trim()
        .parse::<i64>()
        .ok()
        .unwrap_or(fallback)
}

fn get_setting_bool(conn: &Connection, key: &str, fallback: bool) -> bool {
    let raw = get_setting_text(conn, key, if fallback { "1" } else { "0" });
    let clean = raw.trim().to_lowercase();
    matches!(clean.as_str(), "1" | "true" | "si" | "yes" | "on")
}

fn upsert_setting(conn: &Connection, key: &str, value: &str) -> Result<(), String> {
    conn.execute(
        "
        INSERT INTO settings(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    ",
        params![key, value],
    )
    .map_err(|e| db_error("No se pudo actualizar configuracion", e))?;
    Ok(())
}

fn default_due_date_from_now() -> String {
    (Local::now().date_naive() + chrono::Duration::days(DEFAULT_DUE_DAYS))
        .format("%Y-%m-%d")
        .to_string()
}

fn parse_due_date_or_default(raw: Option<String>) -> Result<String, String> {
    if let Some(value) = raw {
        let clean = value.trim();
        if clean.is_empty() {
            return Ok(default_due_date_from_now());
        }
        let parsed = NaiveDate::parse_from_str(clean, "%Y-%m-%d")
            .map_err(|_| "Fecha de vencimiento invalida. Usa formato YYYY-MM-DD".to_string())?;
        return Ok(parsed.format("%Y-%m-%d").to_string());
    }
    Ok(default_due_date_from_now())
}

fn month_bounds(month_key: &str) -> Result<(String, String), String> {
    let first_day = NaiveDate::parse_from_str(&format!("{month_key}-01"), "%Y-%m-%d")
        .map_err(|_| "Mes invalido para comparativa".to_string())?;
    let next_month = if first_day.month() == 12 {
        NaiveDate::from_ymd_opt(first_day.year() + 1, 1, 1)
    } else {
        NaiveDate::from_ymd_opt(first_day.year(), first_day.month() + 1, 1)
    }
    .ok_or_else(|| "No se pudo calcular mes siguiente".to_string())?;

    Ok((
        first_day.format("%Y-%m-%dT00:00:00").to_string(),
        next_month.format("%Y-%m-%dT00:00:00").to_string(),
    ))
}

fn format_ticket_amount(value: f64) -> String {
    format!("{:.0}", round_integer(value))
}

fn read_ticket_settings(conn: &Connection) -> TicketSettingsResponse {
    let width_raw = get_setting_i64(conn, TICKET_PAPER_WIDTH_KEY, 58);
    let width = if width_raw >= 80 { 80 } else { 58 };
    TicketSettingsResponse {
        store_name: get_setting_text(conn, TICKET_STORE_NAME_KEY, "BUEN TRAGO"),
        tax_id: get_setting_text(conn, TICKET_TAX_ID_KEY, ""),
        address: get_setting_text(conn, TICKET_ADDRESS_KEY, ""),
        phone: get_setting_text(conn, TICKET_PHONE_KEY, ""),
        header_text: get_setting_text(conn, TICKET_HEADER_KEY, "Gracias por tu compra"),
        footer_text: get_setting_text(conn, TICKET_FOOTER_KEY, "Vuelve pronto"),
        paper_width_mm: width,
        logo_path: get_setting_text(conn, TICKET_LOGO_PATH_KEY, ""),
        show_logo: get_setting_bool(conn, TICKET_SHOW_LOGO_KEY, false),
    }
}

fn read_backup_config(conn: &Connection) -> BackupConfigResponse {
    BackupConfigResponse {
        auto_enabled: get_setting_bool(conn, BACKUP_AUTO_ENABLED_KEY, true),
        interval_hours: get_setting_i64(conn, BACKUP_INTERVAL_HOURS_KEY, 12).clamp(1, 168),
        retention_count: get_setting_i64(conn, BACKUP_RETENTION_COUNT_KEY, 30).clamp(1, 400),
        last_run_at: {
            let value = get_setting_text(conn, BACKUP_LAST_RUN_AT_KEY, "");
            if value.trim().is_empty() {
                None
            } else {
                Some(value)
            }
        },
    }
}

fn compute_delta_percent(current: f64, previous: f64) -> f64 {
    if previous.abs() <= 1e-9 {
        if current.abs() <= 1e-9 {
            0.0
        } else {
            100.0
        }
    } else {
        ((current - previous) / previous) * 100.0
    }
}

fn summarize_month(conn: &Connection, month_key: &str) -> Result<DashboardCompareBlock, String> {
    let (
        gross_total,
        paid_total,
        due_total,
        sales_count,
        internal_consumption_total,
        internal_operations_count,
    ): (f64, f64, f64, i64, f64, i64) = conn
        .query_row(
            "
            SELECT
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') <> 'internal' THEN total ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') <> 'internal' THEN paid_amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') <> 'internal' THEN balance_due ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') <> 'internal' THEN 1 ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') = 'internal' THEN total ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') = 'internal' THEN 1 ELSE 0 END), 0)
            FROM sales
            WHERE substr(sold_at, 1, 7) = ?
        ",
            params![month_key],
            |row| {
                Ok((
                    row.get(0)?,
                    row.get(1)?,
                    row.get(2)?,
                    row.get(3)?,
                    row.get(4)?,
                    row.get(5)?,
                ))
            },
        )
        .map_err(|e| db_error("No se pudo resumir ventas por mes", e))?;

    let estimated_profit: f64 = conn
        .query_row(
            "
            SELECT COALESCE(SUM((si.unit_price - si.cost_at_sale) * si.quantity), 0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE substr(s.sold_at, 1, 7) = ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
        ",
            params![month_key],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo resumir ganancia por mes", e))?;
    let net_profit_after_internal = round_integer(estimated_profit - internal_consumption_total);

    let avg_ticket = if sales_count > 0 {
        gross_total / sales_count as f64
    } else {
        0.0
    };

    Ok(DashboardCompareBlock {
        month: month_key.to_string(),
        gross_total,
        paid_total,
        due_total,
        estimated_profit,
        internal_consumption_total,
        internal_operations_count,
        net_profit_after_internal,
        sales_count,
        avg_ticket,
    })
}

fn create_backup_file(
    app: &AppHandle,
    target_path: Option<String>,
) -> Result<CreateBackupResponse, String> {
    let db_path = resolve_db_path(app)?;
    if !db_path.exists() {
        return Err("No existe base de datos para respaldar".to_string());
    }

    let destination = if let Some(raw) = target_path {
        let clean = raw.trim();
        if clean.is_empty() {
            let backup_dir = resolve_backup_dir(app)?;
            fs::create_dir_all(&backup_dir)
                .map_err(|e| db_error("No se pudo crear carpeta de backups", e))?;
            backup_dir.join(format!(
                "venta_backup_{}.db",
                Local::now().format("%Y%m%d_%H%M%S")
            ))
        } else {
            PathBuf::from(clean)
        }
    } else {
        let backup_dir = resolve_backup_dir(app)?;
        fs::create_dir_all(&backup_dir)
            .map_err(|e| db_error("No se pudo crear carpeta de backups", e))?;
        backup_dir.join(format!(
            "venta_backup_{}.db",
            Local::now().format("%Y%m%d_%H%M%S")
        ))
    };

    if destination == db_path {
        return Err("La ruta de backup no puede ser la misma de la base de datos".to_string());
    }
    if let Some(parent) = destination.parent() {
        fs::create_dir_all(parent).map_err(|e| db_error("No se pudo crear carpeta destino", e))?;
    }

    fs::copy(&db_path, &destination).map_err(|e| db_error("No se pudo crear backup", e))?;
    let size_bytes = fs::metadata(&destination)
        .map(|meta| meta.len() as i64)
        .unwrap_or(0_i64);

    Ok(CreateBackupResponse {
        backup_path: destination.to_string_lossy().to_string(),
        size_bytes,
    })
}

fn run_backup_maintenance_internal(
    conn: &Connection,
    app: &AppHandle,
    force: bool,
) -> Result<BackupMaintenanceResponse, String> {
    let config = read_backup_config(conn);
    let now = Local::now();
    let executed_at = now.format("%Y-%m-%dT%H:%M:%S").to_string();

    if !config.auto_enabled && !force {
        return Ok(BackupMaintenanceResponse {
            executed_at,
            created_backup_path: None,
            deleted_files: Vec::new(),
            skipped_reason: Some("Backups automaticos desactivados".to_string()),
        });
    }

    if !force {
        if let Some(last_run) = config.last_run_at.as_deref() {
            if let Ok(last_dt) = NaiveDateTime::parse_from_str(last_run, "%Y-%m-%dT%H:%M:%S") {
                let threshold = last_dt + Duration::hours(config.interval_hours);
                if now.naive_local() < threshold {
                    return Ok(BackupMaintenanceResponse {
                        executed_at,
                        created_backup_path: None,
                        deleted_files: Vec::new(),
                        skipped_reason: Some(
                            "Aun no se cumple el intervalo configurado".to_string(),
                        ),
                    });
                }
            }
        }
    }

    let created = create_backup_file(app, None)?;
    upsert_setting(conn, BACKUP_LAST_RUN_AT_KEY, &executed_at)?;

    let mut files = list_backup_files(app.clone(), Some(1000))?;
    files.sort_by(|a, b| b.modified_at.cmp(&a.modified_at));
    let keep = config.retention_count.max(1) as usize;
    let mut deleted_files = Vec::new();
    if files.len() > keep {
        for item in files.iter().skip(keep) {
            let path = PathBuf::from(&item.path);
            if path.exists() && path.is_file() {
                fs::remove_file(&path)
                    .map_err(|e| db_error("No se pudo limpiar backup viejo", e))?;
                deleted_files.push(item.path.clone());
            }
        }
    }

    Ok(BackupMaintenanceResponse {
        executed_at,
        created_backup_path: Some(created.backup_path),
        deleted_files,
        skipped_reason: None,
    })
}

fn build_sale_ticket_body(
    settings: &TicketSettingsResponse,
    sale_id: i64,
    sold_at: &str,
    customer_name: Option<&str>,
    payment_method: &str,
    total: f64,
    paid_amount: f64,
    balance_due: f64,
    items: &[SaleTicketItem],
    copy_type: &str,
) -> String {
    let mut lines: Vec<String> = Vec::new();
    lines.push(settings.store_name.clone());
    if !settings.tax_id.trim().is_empty() {
        lines.push(format!("CUIT: {}", settings.tax_id.trim()));
    }
    if !settings.address.trim().is_empty() {
        lines.push(settings.address.trim().to_string());
    }
    if !settings.phone.trim().is_empty() {
        lines.push(settings.phone.trim().to_string());
    }
    if !settings.header_text.trim().is_empty() {
        lines.push(settings.header_text.trim().to_string());
    }
    lines.push("------------------------------".to_string());
    lines.push(format!("Ticket #{}", sale_id));
    lines.push(format!("Fecha: {sold_at}"));
    lines.push(format!("Tipo: {}", copy_type.to_uppercase()));
    lines.push(format!(
        "Cliente: {}",
        customer_name.unwrap_or("Consumidor final")
    ));
    lines.push("------------------------------".to_string());
    for item in items {
        lines.push(format!(
            "{} x{}  {}",
            item.product_name,
            format_ticket_amount(item.quantity),
            format_ticket_amount(item.subtotal)
        ));
    }
    lines.push("------------------------------".to_string());
    lines.push(format!("Metodo: {payment_method}"));
    lines.push(format!("TOTAL: {}", format_ticket_amount(total)));
    lines.push(format!("PAGADO: {}", format_ticket_amount(paid_amount)));
    lines.push(format!("DEUDA: {}", format_ticket_amount(balance_due)));
    if !settings.footer_text.trim().is_empty() {
        lines.push("------------------------------".to_string());
        lines.push(settings.footer_text.trim().to_string());
    }
    lines.join("\n")
}

fn resolve_db_path(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(raw) = env::var("VENTA_DB_PATH") {
        let trimmed = raw.trim();
        if !trimmed.is_empty() {
            return Ok(PathBuf::from(trimmed));
        }
    }

    let cwd =
        env::current_dir().map_err(|e| db_error("No se pudo obtener directorio actual", e))?;
    let candidate_local = cwd.join("data").join("venta_local.db");
    if candidate_local.exists() {
        return Ok(candidate_local);
    }

    let candidate_parent = cwd.join("..").join("data").join("venta_local.db");
    if candidate_parent.exists() {
        return Ok(candidate_parent);
    }

    if let Ok(exe_path) = env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let portable_candidate = exe_dir.join("data").join("venta_local.db");
            if portable_candidate.exists() {
                return Ok(portable_candidate);
            }
        }
    }

    let app_data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| db_error("No se pudo resolver app_data_dir", e))?;
    Ok(app_data_dir.join("data").join("venta_local.db"))
}

fn ensure_schema(conn: &Connection) -> Result<(), String> {
    conn.execute_batch(
        "
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            margin_percent REAL NOT NULL DEFAULT 30,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            barcode TEXT UNIQUE,
            category_id INTEGER NOT NULL,
            cost REAL NOT NULL DEFAULT 0,
            sale_price REAL NOT NULL DEFAULT 0,
            auto_price INTEGER NOT NULL DEFAULT 1,
            stock REAL NOT NULL DEFAULT 0,
            min_stock REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            alert_limit REAL NOT NULL DEFAULT 50000,
            notes TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sold_at TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            total REAL NOT NULL,
            notes TEXT,
            customer_id INTEGER,
            sale_type TEXT NOT NULL DEFAULT 'cash',
            paid_amount REAL NOT NULL DEFAULT 0,
            balance_due REAL NOT NULL DEFAULT 0,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'paid',
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            subtotal REAL NOT NULL,
            cost_at_sale REAL NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            note TEXT,
            reference_type TEXT,
            reference_id INTEGER,
            FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE SET NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            stock_before REAL NOT NULL,
            stock_after REAL NOT NULL,
            unit_cost REAL,
            reference_type TEXT,
            reference_id INTEGER,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            password TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS deleted_category_archives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            margin_percent REAL NOT NULL,
            deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_by_user_id INTEGER,
            FOREIGN KEY (deleted_by_user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS sale_reversals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL UNIQUE,
            sold_at TEXT,
            payment_method TEXT,
            sale_type TEXT,
            status TEXT,
            customer_id INTEGER,
            total REAL NOT NULL DEFAULT 0,
            paid_amount REAL NOT NULL DEFAULT 0,
            balance_due REAL NOT NULL DEFAULT 0,
            items_count INTEGER NOT NULL DEFAULT 0,
            reversed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reversed_by_user_id INTEGER,
            reason TEXT,
            FOREIGN KEY (reversed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS stock_movement_reversals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movement_id INTEGER NOT NULL UNIQUE,
            reversal_movement_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            reversed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reversed_by_user_id INTEGER,
            reason TEXT,
            FOREIGN KEY (movement_id) REFERENCES stock_movements(id) ON DELETE CASCADE,
            FOREIGN KEY (reversal_movement_id) REFERENCES stock_movements(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
            FOREIGN KEY (reversed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS product_favorites (
            product_id INTEGER PRIMARY KEY,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS ticket_prints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            printed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            printed_by_user_id INTEGER,
            copy_type TEXT NOT NULL DEFAULT 'original',
            FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
            FOREIGN KEY (printed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
        CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
        CREATE INDEX IF NOT EXISTS idx_sales_sold_at ON sales(sold_at);
        CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
        CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id);
        CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id);
        CREATE INDEX IF NOT EXISTS idx_stock_movements_created_at ON stock_movements(created_at);
        CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
        CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
        CREATE INDEX IF NOT EXISTS idx_deleted_category_archives_deleted_at ON deleted_category_archives(deleted_at);
        CREATE INDEX IF NOT EXISTS idx_sale_reversals_reversed_at ON sale_reversals(reversed_at);
        CREATE INDEX IF NOT EXISTS idx_stock_movement_reversals_reversed_at ON stock_movement_reversals(reversed_at);
        CREATE INDEX IF NOT EXISTS idx_ticket_prints_sale ON ticket_prints(sale_id);
        CREATE INDEX IF NOT EXISTS idx_ticket_prints_printed_at ON ticket_prints(printed_at);
    ",
    )
    .map_err(|e| db_error("No se pudo preparar esquema", e))?;

    if !table_has_column(conn, "sales", "due_date")? {
        conn.execute("ALTER TABLE sales ADD COLUMN due_date TEXT", [])
            .map_err(|e| db_error("No se pudo agregar columna due_date en sales", e))?;
    }
    ensure_column_exists(
        conn,
        "sales",
        "sale_type",
        "TEXT NOT NULL DEFAULT 'cash'",
        "No se pudo agregar columna sale_type en sales",
    )?;
    ensure_column_exists(
        conn,
        "sales",
        "paid_amount",
        "REAL NOT NULL DEFAULT 0",
        "No se pudo agregar columna paid_amount en sales",
    )?;
    ensure_column_exists(
        conn,
        "sales",
        "balance_due",
        "REAL NOT NULL DEFAULT 0",
        "No se pudo agregar columna balance_due en sales",
    )?;
    ensure_column_exists(
        conn,
        "sales",
        "status",
        "TEXT NOT NULL DEFAULT 'paid'",
        "No se pudo agregar columna status en sales",
    )?;

    ensure_column_exists(
        conn,
        "users",
        "display_name",
        "TEXT",
        "No se pudo agregar columna display_name en users",
    )?;
    ensure_column_exists(
        conn,
        "users",
        "role",
        "TEXT NOT NULL DEFAULT 'seller'",
        "No se pudo agregar columna role en users",
    )?;
    ensure_column_exists(
        conn,
        "users",
        "password",
        "TEXT",
        "No se pudo agregar columna password en users",
    )?;
    ensure_column_exists(
        conn,
        "users",
        "updated_at",
        "TEXT",
        "No se pudo agregar columna updated_at en users",
    )?;
    ensure_column_exists(
        conn,
        "users",
        "created_at",
        "TEXT",
        "No se pudo agregar columna created_at en users",
    )?;
    ensure_column_exists(
        conn,
        "users",
        "active",
        "INTEGER NOT NULL DEFAULT 1",
        "No se pudo agregar columna active en users",
    )?;

    conn.execute(
        "
        UPDATE users
        SET
            display_name = COALESCE(NULLIF(TRIM(display_name), ''), username),
            active = COALESCE(active, 1),
            created_at = COALESCE(NULLIF(TRIM(created_at), ''), CURRENT_TIMESTAMP),
            updated_at = COALESCE(NULLIF(TRIM(updated_at), ''), CURRENT_TIMESTAMP),
            password = COALESCE(password, '')
    ",
        [],
    )
    .map_err(|e| db_error("No se pudo normalizar columnas de users", e))?;

    conn.execute(
        "
        UPDATE users
        SET role = CASE
            WHEN lower(trim(role)) IN ('admin', 'administrador') THEN 'admin'
            WHEN lower(trim(role)) IN ('seller', 'vendedor') THEN 'seller'
            ELSE 'seller'
        END
    ",
        [],
    )
    .map_err(|e| db_error("No se pudo normalizar roles de users", e))?;

    conn.execute(
        "
        INSERT INTO settings(key, value) VALUES('rounding_base', '100')
        ON CONFLICT(key) DO NOTHING
    ",
        [],
    )
    .map_err(|e| db_error("No se pudo asegurar setting rounding_base", e))?;

    let default_settings = [
        (TICKET_STORE_NAME_KEY, "BUEN TRAGO"),
        (TICKET_TAX_ID_KEY, ""),
        (TICKET_ADDRESS_KEY, ""),
        (TICKET_PHONE_KEY, ""),
        (TICKET_HEADER_KEY, "Gracias por tu compra"),
        (TICKET_FOOTER_KEY, "Vuelve pronto"),
        (TICKET_PAPER_WIDTH_KEY, "58"),
        (TICKET_LOGO_PATH_KEY, ""),
        (TICKET_SHOW_LOGO_KEY, "0"),
        (BACKUP_AUTO_ENABLED_KEY, "1"),
        (BACKUP_INTERVAL_HOURS_KEY, "12"),
        (BACKUP_RETENTION_COUNT_KEY, "30"),
    ];
    for (key, value) in default_settings {
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO NOTHING",
            params![key, value],
        )
        .map_err(|e| db_error("No se pudo asegurar configuracion por defecto", e))?;
    }

    conn.execute(
        "
        UPDATE settings
        SET value = 'BUEN TRAGO'
        WHERE key = ? AND upper(trim(value)) = 'ALTO TRAGO'
    ",
        params![TICKET_STORE_NAME_KEY],
    )
    .map_err(|e| db_error("No se pudo migrar nombre comercial por defecto", e))?;

    let category_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM categories", [], |row| row.get(0))
        .map_err(|e| db_error("No se pudo contar categorias", e))?;

    if category_count <= 0 {
        let defaults = [
            ("Vinos", 30.0f64),
            ("Gaseosas", 35.0f64),
            ("Papel higienico", 50.0f64),
        ];
        for (name, margin) in defaults {
            conn.execute(
                "INSERT INTO categories(name, margin_percent) VALUES (?, ?)",
                params![name, margin],
            )
            .map_err(|e| db_error("No se pudo insertar categoria por defecto", e))?;
        }
    }

    ensure_default_users(conn)?;

    Ok(())
}

fn open_db(app: &AppHandle) -> Result<Connection, String> {
    let db_path = resolve_db_path(app)?;
    if let Some(parent) = db_path.parent() {
        fs::create_dir_all(parent).map_err(|e| db_error("No se pudo crear carpeta de datos", e))?;
    }
    let conn = Connection::open(db_path).map_err(|e| db_error("No se pudo abrir SQLite", e))?;
    ensure_schema(&conn)?;
    Ok(conn)
}

fn normalize_username(raw: &str) -> String {
    raw.trim().to_lowercase()
}

fn normalize_user_role(raw: &str) -> Result<String, String> {
    let clean = raw
        .trim()
        .to_lowercase()
        .replace('\u{00E1}', "a")
        .replace('\u{00E9}', "e")
        .replace('\u{00ED}', "i")
        .replace('\u{00F3}', "o")
        .replace('\u{00FA}', "u");
    let normalized = match clean.as_str() {
        "admin" | "administrador" => "admin",
        "seller" | "vendedor" => "seller",
        _ => return Err("Rol invalido. Usa admin o seller".to_string()),
    };
    Ok(normalized.to_string())
}

fn ensure_default_user(
    conn: &Connection,
    username: &str,
    display_name: &str,
    role: &str,
    default_password: &str,
) -> Result<(), String> {
    let existing = conn
        .query_row(
            "
            SELECT
                id,
                COALESCE(password, '') AS password,
                COALESCE(display_name, '') AS display_name
            FROM users
            WHERE username = ?
            ORDER BY id ASC
            LIMIT 1
        ",
            params![username],
            |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                ))
            },
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar usuario por defecto", e))?;

    if let Some((user_id, existing_password, existing_display_name)) = existing {
        let next_password = if existing_password.trim().is_empty() {
            default_password.to_string()
        } else {
            existing_password
        };
        let next_display_name = if existing_display_name.trim().is_empty() {
            display_name.to_string()
        } else {
            existing_display_name
        };
        conn.execute(
            "
            UPDATE users
            SET display_name = ?, role = ?, password = ?, active = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ",
            params![next_display_name, role, next_password, user_id],
        )
        .map_err(|e| db_error("No se pudo actualizar usuario por defecto", e))?;
    } else {
        conn.execute(
            "
            INSERT INTO users(username, display_name, role, password, active, updated_at)
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ",
            params![username, display_name, role, default_password],
        )
        .map_err(|e| db_error("No se pudo crear usuario por defecto", e))?;
    }

    Ok(())
}

fn ensure_default_users(conn: &Connection) -> Result<(), String> {
    ensure_default_user(conn, "admin", "Administrador", "admin", "admin")
        .map_err(|e| format!("No se pudo asegurar usuario admin por defecto: {e}"))?;
    ensure_default_user(conn, "usuario", "Usuario", "seller", "usuario")
        .map_err(|e| format!("No se pudo asegurar usuario vendedor por defecto: {e}"))?;
    Ok(())
}

fn count_active_admins(conn: &Connection) -> Result<i64, String> {
    conn.query_row(
        "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1",
        [],
        |row| row.get(0),
    )
    .map_err(|e| db_error("No se pudo contar usuarios admin activos", e))
}

fn count_users(conn: &Connection) -> Result<i64, String> {
    conn.query_row("SELECT COUNT(*) FROM users", [], |row| row.get(0))
        .map_err(|e| db_error("No se pudo contar usuarios", e))
}

fn read_user_row(conn: &Connection, user_id: i64) -> Result<UserRow, String> {
    conn.query_row(
        "
        SELECT id, username, display_name, role, active, created_at, updated_at
        FROM users
        WHERE id = ?
        LIMIT 1
    ",
        params![user_id],
        |row| {
            Ok(UserRow {
                id: row.get(0)?,
                username: row.get(1)?,
                display_name: row.get(2)?,
                role: row.get(3)?,
                active: row.get::<_, i64>(4)? == 1,
                created_at: row.get(5)?,
                updated_at: row.get(6)?,
            })
        },
    )
    .optional()
    .map_err(|e| db_error("No se pudo consultar usuario", e))?
    .ok_or_else(|| "Usuario no encontrado".to_string())
}

fn read_session_user(conn: &Connection, user_id: i64) -> Result<Option<SessionUser>, String> {
    conn.query_row(
        "
        SELECT id, username, display_name, role
        FROM users
        WHERE id = ? AND active = 1
        LIMIT 1
    ",
        params![user_id],
        |row| {
            Ok(SessionUser {
                id: row.get(0)?,
                username: row.get(1)?,
                display_name: row.get(2)?,
                role: row.get(3)?,
            })
        },
    )
    .optional()
    .map_err(|e| db_error("No se pudo consultar sesion de usuario", e))
}

fn set_session_user_id(conn: &Connection, user_id: Option<i64>) -> Result<(), String> {
    if let Some(id) = user_id {
        conn.execute(
            "
            INSERT INTO settings(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        ",
            params![SESSION_USER_ID_KEY, id.to_string()],
        )
        .map_err(|e| db_error("No se pudo guardar sesion", e))?;
        return Ok(());
    }

    conn.execute(
        "DELETE FROM settings WHERE key = ?",
        params![SESSION_USER_ID_KEY],
    )
    .map_err(|e| db_error("No se pudo limpiar sesion", e))?;
    Ok(())
}

fn load_session_user(conn: &Connection) -> Result<Option<SessionUser>, String> {
    let raw_user_id: Option<String> = conn
        .query_row(
            "SELECT value FROM settings WHERE key = ? LIMIT 1",
            params![SESSION_USER_ID_KEY],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| db_error("No se pudo leer sesion guardada", e))?;

    let Some(raw) = raw_user_id else {
        return Ok(None);
    };

    let parsed_id = raw.trim().parse::<i64>().ok();
    let Some(user_id) = parsed_id else {
        set_session_user_id(conn, None)?;
        return Ok(None);
    };

    let user = read_session_user(conn, user_id)?;
    if user.is_none() {
        set_session_user_id(conn, None)?;
    }
    Ok(user)
}

fn require_authenticated_user(conn: &Connection) -> Result<SessionUser, String> {
    load_session_user(conn)?
        .ok_or_else(|| "Sesion requerida. Inicia sesion para continuar.".to_string())
}

fn require_admin_user(conn: &Connection) -> Result<SessionUser, String> {
    let user = require_authenticated_user(conn)?;
    if user.role != "admin" {
        return Err("Acceso denegado. Requiere usuario admin.".to_string());
    }
    Ok(user)
}

fn resolve_backup_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let db_path = resolve_db_path(app)?;
    if let Some(parent) = db_path.parent() {
        return Ok(parent.join("backups"));
    }
    let app_data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| db_error("No se pudo resolver app_data_dir para backups", e))?;
    Ok(app_data_dir.join("backups"))
}

fn format_modified_time(path: &Path) -> Option<String> {
    let metadata = fs::metadata(path).ok()?;
    let modified = metadata.modified().ok()?;
    let local_time: DateTime<Local> = DateTime::from(modified);
    Some(local_time.format("%Y-%m-%dT%H:%M:%S").to_string())
}

fn read_category_admin(
    conn: &Connection,
    category_id: i64,
) -> Result<CategoryAdminSummary, String> {
    conn.query_row(
        "
        SELECT
            c.id, c.name, c.margin_percent,
            COALESCE(SUM(CASE WHEN p.active = 1 THEN 1 ELSE 0 END), 0) AS product_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id
        WHERE c.id = ?
        GROUP BY c.id, c.name, c.margin_percent
    ",
        params![category_id],
        |row| {
            Ok(CategoryAdminSummary {
                id: row.get(0)?,
                name: row.get(1)?,
                margin_percent: row.get(2)?,
                product_count: row.get(3)?,
            })
        },
    )
    .optional()
    .map_err(|e| db_error("No se pudo consultar categoria", e))?
    .ok_or_else(|| "Categoria no encontrada".to_string())
}

fn read_product_admin(conn: &Connection, product_id: i64) -> Result<ProductAdminRow, String> {
    conn.query_row(
        "
        SELECT
            p.id, p.name, p.barcode, p.category_id, c.name,
            p.cost, p.sale_price, p.auto_price, p.stock, p.min_stock, p.active
        FROM products p
        JOIN categories c ON c.id = p.category_id
        WHERE p.id = ?
        LIMIT 1
    ",
        params![product_id],
        |row| {
            Ok(ProductAdminRow {
                id: row.get(0)?,
                name: row.get(1)?,
                barcode: row.get(2)?,
                category_id: row.get(3)?,
                category_name: row.get(4)?,
                cost: row.get(5)?,
                sale_price: row.get(6)?,
                auto_price: row.get::<_, i64>(7)? == 1,
                stock: row.get(8)?,
                min_stock: row.get(9)?,
                active: row.get::<_, i64>(10)? == 1,
            })
        },
    )
    .optional()
    .map_err(|e| db_error("No se pudo consultar producto", e))?
    .ok_or_else(|| "Producto no encontrado".to_string())
}

fn get_rounding_base(conn: &Connection) -> i64 {
    let value: Option<String> = conn
        .query_row(
            "SELECT value FROM settings WHERE key = 'rounding_base' LIMIT 1",
            [],
            |row| row.get(0),
        )
        .optional()
        .ok()
        .flatten();

    value
        .as_deref()
        .and_then(|text| text.parse::<i64>().ok())
        .filter(|parsed| *parsed > 0)
        .unwrap_or(100)
}

fn calculate_auto_price(cost: f64, margin_percent: f64, rounding_base: i64) -> f64 {
    let base = if rounding_base <= 0 {
        100.0
    } else {
        rounding_base as f64
    };
    let raw = cost + (cost * (margin_percent / 100.0));
    ((raw / base).round()) * base
}

fn normalize_payment_method(raw: &str) -> Result<String, String> {
    let clean = raw
        .trim()
        .to_lowercase()
        .replace('\u{00E1}', "a")
        .replace('\u{00E9}', "e")
        .replace('\u{00ED}', "i")
        .replace('\u{00F3}', "o")
        .replace('\u{00FA}', "u");
    let normalized = match clean.as_str() {
        "efectivo" => "Efectivo",
        "debito" => "Debito",
        "credito" => "Credito",
        "transferencia" => "Transferencia",
        "deuda" | "cuenta corriente" | "cuenta_corriente" => "Deuda",
        "consumo interno" | "consumo_interno" | "interno" => "Consumo interno",
        _ => return Err("Metodo de pago invalido".to_string()),
    };
    Ok(normalized.to_string())
}

fn normalize_inventory_movement_type(raw: &str) -> Result<String, String> {
    let clean = raw
        .trim()
        .to_lowercase()
        .replace('\u{00E1}', "a")
        .replace('\u{00E9}', "e")
        .replace('\u{00ED}', "i")
        .replace('\u{00F3}', "o")
        .replace('\u{00FA}', "u");
    let normalized = match clean.as_str() {
        "manual_in" | "entrada" | "ingreso" => "manual_in",
        "manual_out" | "salida" | "egreso" => "manual_out",
        "adjustment" | "ajuste" => "adjustment",
        _ => return Err("Tipo de movimiento invalido".to_string()),
    };
    Ok(normalized.to_string())
}

fn normalize_inventory_movement_filter_type(raw: &str) -> Result<String, String> {
    let clean = raw
        .trim()
        .to_lowercase()
        .replace('\u{00E1}', "a")
        .replace('\u{00E9}', "e")
        .replace('\u{00ED}', "i")
        .replace('\u{00F3}', "o")
        .replace('\u{00FA}', "u");
    let normalized = match clean.as_str() {
        "manual_in" | "entrada" | "ingreso" => "manual_in",
        "manual_out" | "salida" | "egreso" => "manual_out",
        "adjustment" | "ajuste" => "adjustment",
        "sale" | "venta" => "sale",
        _ => return Err("Tipo de movimiento invalido".to_string()),
    };
    Ok(normalized.to_string())
}

fn resolve_month_key(month: Option<String>) -> Result<String, String> {
    if let Some(raw) = month {
        let clean = raw.trim();
        if clean.is_empty() {
            return Ok(Local::now().format("%Y-%m").to_string());
        }
        let parsed = NaiveDate::parse_from_str(&format!("{clean}-01"), "%Y-%m-%d")
            .map_err(|_| "Mes invalido. Usa formato YYYY-MM".to_string())?;
        return Ok(parsed.format("%Y-%m").to_string());
    }

    Ok(Local::now().format("%Y-%m").to_string())
}

fn resolve_report_range(from_date: &str, to_date: &str) -> Result<(String, String), String> {
    let clean_from = from_date.trim();
    let clean_to = to_date.trim();
    if clean_from.is_empty() || clean_to.is_empty() {
        return Err("Debes indicar fecha desde y fecha hasta".to_string());
    }

    let parsed_from = NaiveDate::parse_from_str(clean_from, "%Y-%m-%d")
        .map_err(|_| "Fecha desde invalida. Usa formato YYYY-MM-DD".to_string())?;
    let parsed_to = NaiveDate::parse_from_str(clean_to, "%Y-%m-%d")
        .map_err(|_| "Fecha hasta invalida. Usa formato YYYY-MM-DD".to_string())?;
    if parsed_to < parsed_from {
        return Err("La fecha hasta no puede ser menor que la fecha desde".to_string());
    }

    let next_day = parsed_to
        .succ_opt()
        .ok_or_else(|| "No se pudo resolver rango final de fecha".to_string())?;
    let start_ts = parsed_from.format("%Y-%m-%dT00:00:00").to_string();
    let end_ts = next_day.format("%Y-%m-%dT00:00:00").to_string();
    Ok((start_ts, end_ts))
}

#[tauri::command]
fn health_check() -> String {
    "ok".to_string()
}

#[tauri::command]
fn payment_methods(app: AppHandle) -> Result<Vec<String>, String> {
    let conn = open_db(&app)?;
    let _session = require_authenticated_user(&conn)?;
    Ok(vec![
        "Efectivo".to_string(),
        "Credito".to_string(),
        "Debito".to_string(),
        "Transferencia".to_string(),
        "Deuda".to_string(),
        "Consumo interno".to_string(),
    ])
}

#[tauri::command]
fn auth_bootstrap_status(app: AppHandle) -> Result<AuthBootstrapStatusResponse, String> {
    let conn = open_db(&app)?;
    let users_count = count_users(&conn)?;
    Ok(AuthBootstrapStatusResponse {
        needs_setup: users_count <= 0,
        users_count,
    })
}

#[tauri::command]
fn auth_bootstrap_create_admin(
    app: AppHandle,
    payload: AuthBootstrapCreateRequest,
) -> Result<AuthSessionResponse, String> {
    let conn = open_db(&app)?;
    let existing = count_users(&conn)?;
    if existing > 0 {
        return Err("La configuracion inicial ya fue completada.".to_string());
    }

    let username = normalize_username(&payload.username);
    if username.is_empty() {
        return Err("El usuario es obligatorio".to_string());
    }
    if username.contains(' ') {
        return Err("El usuario no puede contener espacios".to_string());
    }

    let display_name = payload.display_name.trim().to_string();
    if display_name.is_empty() {
        return Err("El nombre visible es obligatorio".to_string());
    }

    let password = payload.password.trim().to_string();
    if password.len() < 4 {
        return Err("La clave inicial debe tener al menos 4 caracteres".to_string());
    }

    conn.execute(
        "
        INSERT INTO users(username, display_name, role, password, active, updated_at)
        VALUES (?, ?, 'admin', ?, 1, CURRENT_TIMESTAMP)
    ",
        params![username, display_name, password],
    )
    .map_err(|e| {
        db_error(
            "No se pudo crear usuario administrador inicial (username duplicado o datos invalidos)",
            e,
        )
    })?;

    let user_id = conn.last_insert_rowid();
    set_session_user_id(&conn, Some(user_id))?;
    let user = read_session_user(&conn, user_id)?;
    Ok(AuthSessionResponse {
        authenticated: user.is_some(),
        user,
    })
}

#[tauri::command]
fn auth_session(app: AppHandle) -> Result<AuthSessionResponse, String> {
    let conn = open_db(&app)?;
    let user = load_session_user(&conn)?;
    Ok(AuthSessionResponse {
        authenticated: user.is_some(),
        user,
    })
}

#[tauri::command]
fn auth_login(app: AppHandle, payload: LoginRequest) -> Result<AuthSessionResponse, String> {
    let conn = open_db(&app)?;
    let username = normalize_username(&payload.username);
    let password = payload.password.trim().to_string();

    if username.is_empty() || password.is_empty() {
        return Err("Usuario y clave son obligatorios".to_string());
    }

    let has_display_name = table_has_column(&conn, "users", "display_name")?;
    let has_role = table_has_column(&conn, "users", "role")?;
    let has_active = table_has_column(&conn, "users", "active")?;
    let has_password = table_has_column(&conn, "users", "password")?;
    let has_password_hash = table_has_column(&conn, "users", "password_hash")?;

    let display_name_expr = if has_display_name {
        "COALESCE(NULLIF(TRIM(display_name), ''), username)"
    } else {
        "username"
    };
    let role_expr = if has_role {
        "COALESCE(NULLIF(TRIM(role), ''), 'seller')"
    } else {
        "'seller'"
    };
    let password_expr = if has_password {
        "COALESCE(password, '')"
    } else {
        "''"
    };
    let password_hash_expr = if has_password_hash {
        "COALESCE(password_hash, '')"
    } else {
        "''"
    };
    let active_filter = if has_active { "AND active = 1" } else { "" };
    let login_sql = format!(
        "
        SELECT
            id,
            username,
            {display_name_expr} AS display_name,
            {role_expr} AS role,
            {password_expr} AS password,
            {password_hash_expr} AS password_hash
        FROM users
        WHERE username = ? {active_filter}
        LIMIT 1
    "
    );

    let row = conn
        .query_row(&login_sql, params![username], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, String>(4)?,
                row.get::<_, String>(5)?,
            ))
        })
        .optional()
        .map_err(|e| db_error("No se pudo validar login", e))?
        .ok_or_else(|| "Usuario o clave incorrectos".to_string())?;

    let (user_id, db_username, display_name, raw_role, plain_password, legacy_hash) = row;
    let role = normalize_user_role(&raw_role).unwrap_or_else(|_| "seller".to_string());
    let plain_ok = !plain_password.is_empty() && plain_password == password;
    let legacy_ok = verify_legacy_password(&password, &legacy_hash);
    if !plain_ok && !legacy_ok {
        return Err("Usuario o clave incorrectos".to_string());
    }

    if legacy_ok && plain_password.is_empty() {
        let _ = conn.execute(
            "
            UPDATE users
            SET password = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ",
            params![password, user_id],
        );
    }

    if role != raw_role {
        let _ = conn.execute(
            "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            params![role, user_id],
        );
    }

    let user = SessionUser {
        id: user_id,
        username: db_username,
        display_name,
        role,
    };

    set_session_user_id(&conn, Some(user_id))?;

    Ok(AuthSessionResponse {
        authenticated: true,
        user: Some(user),
    })
}

#[tauri::command]
fn auth_logout(app: AppHandle) -> Result<AuthSessionResponse, String> {
    let conn = open_db(&app)?;
    set_session_user_id(&conn, None)?;
    Ok(AuthSessionResponse {
        authenticated: false,
        user: None,
    })
}

#[tauri::command]
fn list_users(app: AppHandle, include_inactive: Option<bool>) -> Result<Vec<UserRow>, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let include = if include_inactive.unwrap_or(true) {
        1_i64
    } else {
        0_i64
    };

    let mut stmt = conn
        .prepare(
            "
            SELECT id, username, display_name, role, active, created_at, updated_at
            FROM users
            WHERE (? = 1 OR active = 1)
            ORDER BY role ASC, username ASC
        ",
        )
        .map_err(|e| db_error("No se pudo preparar listado de usuarios", e))?;

    let rows = stmt
        .query_map(params![include], |row| {
            Ok(UserRow {
                id: row.get(0)?,
                username: row.get(1)?,
                display_name: row.get(2)?,
                role: row.get(3)?,
                active: row.get::<_, i64>(4)? == 1,
                created_at: row.get(5)?,
                updated_at: row.get(6)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar usuarios", e))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear usuario", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn create_user(app: AppHandle, payload: CreateUserRequest) -> Result<UserRow, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let username = normalize_username(&payload.username);
    if username.is_empty() {
        return Err("El username es obligatorio".to_string());
    }
    if username.contains(' ') {
        return Err("El username no puede contener espacios".to_string());
    }

    let display_name = payload.display_name.trim().to_string();
    if display_name.is_empty() {
        return Err("El nombre visible es obligatorio".to_string());
    }

    let role = normalize_user_role(&payload.role)?;
    let password = payload.password.trim().to_string();
    if password.is_empty() {
        return Err("La clave del usuario es obligatoria".to_string());
    }

    conn.execute(
        "
        INSERT INTO users(username, display_name, role, password, active, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ",
        params![
            username,
            display_name,
            role,
            password,
            if payload.active { 1 } else { 0 }
        ],
    )
    .map_err(|e| {
        db_error(
            "No se pudo crear usuario (username duplicado o datos invalidos)",
            e,
        )
    })?;

    let user_id = conn.last_insert_rowid();
    read_user_row(&conn, user_id)
}

#[tauri::command]
fn update_user(app: AppHandle, payload: UpdateUserRequest) -> Result<UserRow, String> {
    if payload.id <= 0 {
        return Err("Usuario invalido".to_string());
    }

    let mut conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let current = conn
        .query_row(
            "SELECT role, active FROM users WHERE id = ? LIMIT 1",
            params![payload.id],
            |row| Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?)),
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar usuario actual", e))?
        .ok_or_else(|| "Usuario no encontrado".to_string())?;

    let username = normalize_username(&payload.username);
    if username.is_empty() {
        return Err("El username es obligatorio".to_string());
    }
    if username.contains(' ') {
        return Err("El username no puede contener espacios".to_string());
    }

    let display_name = payload.display_name.trim().to_string();
    if display_name.is_empty() {
        return Err("El nombre visible es obligatorio".to_string());
    }

    let next_role = normalize_user_role(&payload.role)?;
    let next_active = payload.active;

    if current.0 == "admin" && current.1 == 1 && (!next_active || next_role != "admin") {
        let admins = count_active_admins(&conn)?;
        if admins <= 1 {
            return Err("Debe existir al menos un admin activo".to_string());
        }
    }

    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de usuario", e))?;

    let affected = if let Some(password_raw) = payload.password.as_deref() {
        let clean_password = password_raw.trim().to_string();
        if clean_password.is_empty() {
            return Err("La clave no puede ser vacia".to_string());
        }
        tx.execute(
            "
            UPDATE users
            SET username = ?, display_name = ?, role = ?, password = ?, active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ",
            params![
                username,
                display_name,
                next_role,
                clean_password,
                if next_active { 1 } else { 0 },
                payload.id
            ],
        )
        .map_err(|e| db_error("No se pudo actualizar usuario", e))?
    } else {
        tx.execute(
            "
            UPDATE users
            SET username = ?, display_name = ?, role = ?, active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ",
            params![
                username,
                display_name,
                next_role,
                if next_active { 1 } else { 0 },
                payload.id
            ],
        )
        .map_err(|e| db_error("No se pudo actualizar usuario", e))?
    };

    if affected == 0 {
        return Err("Usuario no encontrado".to_string());
    }

    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar actualizacion de usuario", e))?;

    read_user_row(&conn, payload.id)
}

#[tauri::command]
fn delete_user(app: AppHandle, user_id: i64) -> Result<UserDeleteResponse, String> {
    if user_id <= 0 {
        return Err("Usuario invalido".to_string());
    }

    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let current = conn
        .query_row(
            "SELECT role, active FROM users WHERE id = ? LIMIT 1",
            params![user_id],
            |row| Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)?)),
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar usuario para eliminar", e))?
        .ok_or_else(|| "Usuario no encontrado".to_string())?;

    if current.0 == "admin" && current.1 == 1 {
        let admins = count_active_admins(&conn)?;
        if admins <= 1 {
            return Err("No se puede eliminar el ultimo admin activo".to_string());
        }
    }

    let affected = conn
        .execute("DELETE FROM users WHERE id = ?", params![user_id])
        .map_err(|e| db_error("No se pudo eliminar usuario", e))?;
    if affected == 0 {
        return Err("Usuario no encontrado".to_string());
    }

    Ok(UserDeleteResponse { id: user_id })
}

#[tauri::command]
fn backup_status(app: AppHandle) -> Result<BackupStatusResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let db_path = resolve_db_path(&app)?;
    let backup_dir = resolve_backup_dir(&app)?;

    let db_exists = db_path.exists();
    let metadata = fs::metadata(&db_path).ok();
    let db_size_bytes = metadata.as_ref().map_or(0_i64, |meta| meta.len() as i64);
    let db_modified_at = format_modified_time(&db_path);

    Ok(BackupStatusResponse {
        db_path: db_path.to_string_lossy().to_string(),
        backup_dir: backup_dir.to_string_lossy().to_string(),
        db_exists,
        db_size_bytes,
        db_modified_at,
    })
}

#[tauri::command]
fn list_backup_files(app: AppHandle, limit: Option<i64>) -> Result<Vec<BackupFileInfo>, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let backup_dir = resolve_backup_dir(&app)?;
    if !backup_dir.exists() {
        return Ok(Vec::new());
    }

    let safe_limit = limit.unwrap_or(80).clamp(1, 500) as usize;
    let mut files: Vec<BackupFileInfo> = Vec::new();

    let entries =
        fs::read_dir(&backup_dir).map_err(|e| db_error("No se pudo listar backups", e))?;
    for entry in entries {
        let item = entry.map_err(|e| db_error("No se pudo leer archivo de backup", e))?;
        let path = item.path();
        if !path.is_file() {
            continue;
        }

        let filename = path
            .file_name()
            .map(|name| name.to_string_lossy().to_string())
            .unwrap_or_else(|| "backup.db".to_string());

        let ext = path
            .extension()
            .map(|value| value.to_string_lossy().to_lowercase())
            .unwrap_or_default();
        if ext != "db" && ext != "sqlite" {
            continue;
        }

        let size_bytes = fs::metadata(&path)
            .map(|meta| meta.len() as i64)
            .unwrap_or(0_i64);
        files.push(BackupFileInfo {
            path: path.to_string_lossy().to_string(),
            file_name: filename,
            size_bytes,
            modified_at: format_modified_time(&path),
        });
    }

    files.sort_by(|a, b| b.modified_at.cmp(&a.modified_at));
    files.truncate(safe_limit);
    Ok(files)
}

#[tauri::command]
fn create_backup(
    app: AppHandle,
    target_path: Option<String>,
) -> Result<CreateBackupResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    create_backup_file(&app, target_path)
}

#[tauri::command]
fn restore_backup(app: AppHandle, source_path: String) -> Result<RestoreBackupResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let source = PathBuf::from(source_path.trim());
    if source.as_os_str().is_empty() {
        return Err("Debes indicar ruta de backup a restaurar".to_string());
    }
    if !source.exists() {
        return Err("El archivo de backup no existe".to_string());
    }
    if !source.is_file() {
        return Err("La ruta de backup debe ser un archivo".to_string());
    }

    let db_path = resolve_db_path(&app)?;
    if let Some(parent) = db_path.parent() {
        fs::create_dir_all(parent).map_err(|e| db_error("No se pudo crear carpeta de datos", e))?;
    }

    let mut pre_restore_backup_path: Option<String> = None;
    if db_path.exists() {
        let backup_dir = resolve_backup_dir(&app)?;
        fs::create_dir_all(&backup_dir)
            .map_err(|e| db_error("No se pudo crear carpeta de backups", e))?;
        let pre_restore = backup_dir.join(format!(
            "pre_restore_{}.db",
            Local::now().format("%Y%m%d_%H%M%S")
        ));
        fs::copy(&db_path, &pre_restore)
            .map_err(|e| db_error("No se pudo crear backup previo a restaurar", e))?;
        pre_restore_backup_path = Some(pre_restore.to_string_lossy().to_string());
    }

    fs::copy(&source, &db_path).map_err(|e| db_error("No se pudo restaurar backup", e))?;

    let conn =
        Connection::open(&db_path).map_err(|e| db_error("No se pudo abrir DB restaurada", e))?;
    ensure_schema(&conn)?;

    Ok(RestoreBackupResponse {
        db_path: db_path.to_string_lossy().to_string(),
        message: "Backup restaurado correctamente".to_string(),
        pre_restore_backup_path,
    })
}

#[tauri::command]
fn backup_config(app: AppHandle) -> Result<BackupConfigResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    Ok(read_backup_config(&conn))
}

#[tauri::command]
fn update_backup_config(
    app: AppHandle,
    payload: UpdateBackupConfigRequest,
) -> Result<BackupConfigResponse, String> {
    if payload.interval_hours < 1 || payload.interval_hours > 168 {
        return Err("Intervalo invalido. Rango permitido: 1 a 168 horas".to_string());
    }
    if payload.retention_count < 1 || payload.retention_count > 400 {
        return Err("Retencion invalida. Rango permitido: 1 a 400 backups".to_string());
    }

    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;

    upsert_setting(
        &conn,
        BACKUP_AUTO_ENABLED_KEY,
        if payload.auto_enabled { "1" } else { "0" },
    )?;
    upsert_setting(
        &conn,
        BACKUP_INTERVAL_HOURS_KEY,
        &payload.interval_hours.to_string(),
    )?;
    upsert_setting(
        &conn,
        BACKUP_RETENTION_COUNT_KEY,
        &payload.retention_count.to_string(),
    )?;

    Ok(read_backup_config(&conn))
}

#[tauri::command]
fn run_backup_maintenance(
    app: AppHandle,
    force: Option<bool>,
) -> Result<BackupMaintenanceResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    run_backup_maintenance_internal(&conn, &app, force.unwrap_or(false))
}

#[tauri::command]
fn verify_backup_file(app: AppHandle, path: String) -> Result<BackupVerifyResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let clean = path.trim();
    if clean.is_empty() {
        return Err("Debes indicar archivo a verificar".to_string());
    }
    let file_path = PathBuf::from(clean);
    if !file_path.exists() || !file_path.is_file() {
        return Err("El archivo de backup no existe".to_string());
    }
    let backup_conn = Connection::open(&file_path)
        .map_err(|e| db_error("No se pudo abrir backup para verificacion", e))?;
    let check_result: String = backup_conn
        .query_row("PRAGMA quick_check(1)", [], |row| row.get(0))
        .map_err(|e| db_error("No se pudo ejecutar quick_check del backup", e))?;
    let ok = check_result.eq_ignore_ascii_case("ok");
    Ok(BackupVerifyResponse {
        path: file_path.to_string_lossy().to_string(),
        ok,
        message: if ok {
            "Integridad OK (quick_check)".to_string()
        } else {
            format!("quick_check devolvio: {check_result}")
        },
    })
}

#[tauri::command]
fn search_products(
    app: AppHandle,
    term: Option<String>,
    limit: Option<i64>,
) -> Result<Vec<ProductSummary>, String> {
    let conn = open_db(&app)?;
    let _session = require_authenticated_user(&conn)?;
    let safe_limit = limit.unwrap_or(25).clamp(1, 100);
    let clean_term = term.unwrap_or_default().trim().to_string();

    let mut result: Vec<ProductSummary> = Vec::new();
    if clean_term.is_empty() {
        let mut stmt = conn
            .prepare(
                "
                SELECT id, name, barcode, sale_price, stock
                FROM products
                WHERE active = 1
                ORDER BY name
                LIMIT ?
            ",
            )
            .map_err(|e| db_error("No se pudo preparar consulta de productos", e))?;

        let rows = stmt
            .query_map(params![safe_limit], |row| {
                Ok(ProductSummary {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    barcode: row.get(2)?,
                    sale_price: row.get(3)?,
                    stock: row.get(4)?,
                })
            })
            .map_err(|e| db_error("No se pudo listar productos", e))?;

        for row in rows {
            result.push(row.map_err(|e| db_error("No se pudo mapear producto", e))?);
        }
        return Ok(result);
    }

    let like_term = format!("%{clean_term}%");
    let mut stmt = conn
        .prepare(
            "
            SELECT id, name, barcode, sale_price, stock
            FROM products
            WHERE active = 1 AND (name LIKE ? OR barcode LIKE ?)
            ORDER BY name
            LIMIT ?
        ",
        )
        .map_err(|e| db_error("No se pudo preparar busqueda de productos", e))?;

    let rows = stmt
        .query_map(params![like_term, like_term, safe_limit], |row| {
            Ok(ProductSummary {
                id: row.get(0)?,
                name: row.get(1)?,
                barcode: row.get(2)?,
                sale_price: row.get(3)?,
                stock: row.get(4)?,
            })
        })
        .map_err(|e| db_error("No se pudo buscar productos", e))?;

    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear producto", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn get_product_by_barcode(
    app: AppHandle,
    barcode: String,
) -> Result<Option<ProductSummary>, String> {
    let conn = open_db(&app)?;
    let _session = require_authenticated_user(&conn)?;
    let clean = barcode.trim();
    if clean.is_empty() {
        return Ok(None);
    }

    let found = conn
        .query_row(
            "
            SELECT id, name, barcode, sale_price, stock
            FROM products
            WHERE active = 1 AND barcode = ?
            LIMIT 1
        ",
            params![clean],
            |row| {
                Ok(ProductSummary {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    barcode: row.get(2)?,
                    sale_price: row.get(3)?,
                    stock: row.get(4)?,
                })
            },
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar producto por codigo", e))?;

    Ok(found)
}

#[tauri::command]
fn list_favorite_products(
    app: AppHandle,
    limit: Option<i64>,
) -> Result<Vec<FavoriteProductRow>, String> {
    let conn = open_db(&app)?;
    let _session = require_authenticated_user(&conn)?;
    let safe_limit = limit.unwrap_or(18).clamp(1, 80);
    let mut stmt = conn
        .prepare(
            "
            SELECT p.id, p.name, p.barcode, p.sale_price, p.stock
            FROM product_favorites f
            JOIN products p ON p.id = f.product_id
            WHERE p.active = 1
            ORDER BY f.sort_order ASC, p.name ASC
            LIMIT ?
        ",
        )
        .map_err(|e| db_error("No se pudo preparar favoritos", e))?;
    let rows = stmt
        .query_map(params![safe_limit], |row| {
            Ok(FavoriteProductRow {
                product_id: row.get(0)?,
                name: row.get(1)?,
                barcode: row.get(2)?,
                sale_price: row.get(3)?,
                stock: row.get(4)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar favoritos", e))?;
    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear favorito", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn set_product_favorite(
    app: AppHandle,
    product_id: i64,
    favorite: bool,
) -> Result<SetFavoriteProductResponse, String> {
    if product_id <= 0 {
        return Err("Producto invalido".to_string());
    }
    let conn = open_db(&app)?;
    let _session = require_authenticated_user(&conn)?;

    if favorite {
        let exists: Option<i64> = conn
            .query_row(
                "SELECT id FROM products WHERE id = ? AND active = 1 LIMIT 1",
                params![product_id],
                |row| row.get(0),
            )
            .optional()
            .map_err(|e| db_error("No se pudo validar producto favorito", e))?;
        if exists.is_none() {
            return Err("Producto no encontrado o inactivo".to_string());
        }
        let next_order: i64 = conn
            .query_row(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM product_favorites",
                [],
                |row| row.get(0),
            )
            .map_err(|e| db_error("No se pudo calcular orden de favorito", e))?;
        conn.execute(
            "
            INSERT INTO product_favorites(product_id, sort_order)
            VALUES (?, ?)
            ON CONFLICT(product_id) DO NOTHING
        ",
            params![product_id, next_order],
        )
        .map_err(|e| db_error("No se pudo guardar favorito", e))?;
    } else {
        conn.execute(
            "DELETE FROM product_favorites WHERE product_id = ?",
            params![product_id],
        )
        .map_err(|e| db_error("No se pudo quitar favorito", e))?;
    }

    Ok(SetFavoriteProductResponse {
        product_id,
        favorite,
    })
}

#[tauri::command]
fn list_customers(
    app: AppHandle,
    search: Option<String>,
    limit: Option<i64>,
) -> Result<Vec<CustomerSummary>, String> {
    let conn = open_db(&app)?;
    let _session = require_authenticated_user(&conn)?;
    let safe_limit = limit.unwrap_or(100).clamp(1, 400);
    let clean_search = search.unwrap_or_default().trim().to_string();
    let mut result: Vec<CustomerSummary> = Vec::new();

    if clean_search.is_empty() {
        let mut stmt = conn
            .prepare(
                "
                SELECT
                    c.id, c.name, c.alert_limit,
                    COALESCE(SUM(CASE WHEN s.balance_due > 0 THEN s.balance_due ELSE 0 END), 0) AS debt_total,
                    COALESCE(SUM(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN 1 ELSE 0 END), 0) AS overdue_sales_count,
                    COALESCE(SUM(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN s.balance_due ELSE 0 END), 0) AS overdue_total,
                    COALESCE(MAX(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN CAST(julianday('now') - julianday(s.due_date) AS INTEGER) ELSE 0 END), 0) AS max_days_overdue
                FROM customers c
                LEFT JOIN sales s ON s.customer_id = c.id
                WHERE c.active = 1
                GROUP BY c.id, c.name, c.alert_limit
                ORDER BY c.name
                LIMIT ?
            ",
            )
            .map_err(|e| db_error("No se pudo preparar consulta de clientes", e))?;

        let rows = stmt
            .query_map(params![safe_limit], |row| {
                let debt_total: f64 = row.get(3)?;
                let alert_limit: f64 = row.get(2)?;
                Ok(CustomerSummary {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    debt_total,
                    alert_limit,
                    over_limit: debt_total >= alert_limit,
                    overdue_sales_count: row.get(4)?,
                    overdue_total: row.get(5)?,
                    max_days_overdue: row.get(6)?,
                })
            })
            .map_err(|e| db_error("No se pudo listar clientes", e))?;

        for row in rows {
            result.push(row.map_err(|e| db_error("No se pudo mapear cliente", e))?);
        }
        return Ok(result);
    }

    let like_term = format!("%{clean_search}%");
    let mut stmt = conn
        .prepare(
            "
            SELECT
                c.id, c.name, c.alert_limit,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 THEN s.balance_due ELSE 0 END), 0) AS debt_total,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN 1 ELSE 0 END), 0) AS overdue_sales_count,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN s.balance_due ELSE 0 END), 0) AS overdue_total,
                COALESCE(MAX(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN CAST(julianday('now') - julianday(s.due_date) AS INTEGER) ELSE 0 END), 0) AS max_days_overdue
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id
            WHERE c.active = 1 AND (c.name LIKE ? OR c.phone LIKE ?)
            GROUP BY c.id, c.name, c.alert_limit
            ORDER BY c.name
            LIMIT ?
        ",
        )
        .map_err(|e| db_error("No se pudo preparar busqueda de clientes", e))?;

    let rows = stmt
        .query_map(params![like_term, like_term, safe_limit], |row| {
            let debt_total: f64 = row.get(3)?;
            let alert_limit: f64 = row.get(2)?;
            Ok(CustomerSummary {
                id: row.get(0)?,
                name: row.get(1)?,
                debt_total,
                alert_limit,
                over_limit: debt_total >= alert_limit,
                overdue_sales_count: row.get(4)?,
                overdue_total: row.get(5)?,
                max_days_overdue: row.get(6)?,
            })
        })
        .map_err(|e| db_error("No se pudo buscar clientes", e))?;

    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear cliente", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn create_customer(
    app: AppHandle,
    payload: CreateCustomerRequest,
) -> Result<CustomerSummary, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let clean_name = payload.name.trim().to_string();
    if clean_name.is_empty() {
        return Err("El nombre del cliente es obligatorio".to_string());
    }

    let raw_alert_limit = payload.alert_limit.unwrap_or(50000.0);
    if raw_alert_limit < 0.0 {
        return Err("El limite de alerta no puede ser negativo".to_string());
    }
    let alert_limit = round_integer(raw_alert_limit);

    let clean_phone = payload.phone.unwrap_or_default().trim().to_string();
    let clean_email = payload.email.unwrap_or_default().trim().to_string();
    let clean_notes = payload.notes.unwrap_or_default().trim().to_string();

    conn.execute(
        "
        INSERT INTO customers(name, phone, email, alert_limit, notes, active)
        VALUES (?, ?, ?, ?, ?, 1)
    ",
        params![
            clean_name,
            if clean_phone.is_empty() {
                None::<String>
            } else {
                Some(clean_phone)
            },
            if clean_email.is_empty() {
                None::<String>
            } else {
                Some(clean_email)
            },
            alert_limit,
            if clean_notes.is_empty() {
                None::<String>
            } else {
                Some(clean_notes)
            }
        ],
    )
    .map_err(|e| db_error("No se pudo crear cliente", e))?;

    let customer_id = conn.last_insert_rowid();
    Ok(CustomerSummary {
        id: customer_id,
        name: payload.name.trim().to_string(),
        debt_total: 0.0,
        alert_limit,
        over_limit: false,
        overdue_sales_count: 0,
        overdue_total: 0.0,
        max_days_overdue: 0,
    })
}

#[tauri::command]
fn update_customer(
    app: AppHandle,
    payload: UpdateCustomerRequest,
) -> Result<CustomerSummary, String> {
    if payload.customer_id <= 0 {
        return Err("Cliente invalido".to_string());
    }
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;

    let current = conn
        .query_row(
            "SELECT alert_limit, notes, active FROM customers WHERE id = ? LIMIT 1",
            params![payload.customer_id],
            |row| {
                Ok((
                    row.get::<_, f64>(0)?,
                    row.get::<_, Option<String>>(1)?,
                    row.get::<_, i64>(2)?,
                ))
            },
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar cliente para actualizar", e))?
        .ok_or_else(|| "Cliente no encontrado".to_string())?;

    let raw_next_alert = payload.alert_limit.unwrap_or(current.0);
    if raw_next_alert < 0.0 {
        return Err("El limite de alerta no puede ser negativo".to_string());
    }
    let next_alert = round_integer(raw_next_alert);
    let next_notes = payload
        .notes
        .as_deref()
        .map(str::trim)
        .map(|value| value.to_string())
        .or(current.1)
        .unwrap_or_default();
    let next_active = payload.active.unwrap_or(current.2 == 1);

    conn.execute(
        "
        UPDATE customers
        SET alert_limit = ?, notes = ?, active = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ",
        params![
            next_alert,
            if next_notes.is_empty() {
                None::<String>
            } else {
                Some(next_notes)
            },
            if next_active { 1 } else { 0 },
            payload.customer_id
        ],
    )
    .map_err(|e| db_error("No se pudo actualizar cliente", e))?;

    let result = conn
        .query_row(
            "
            SELECT
                c.id, c.name, c.alert_limit,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 THEN s.balance_due ELSE 0 END), 0) AS debt_total,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN 1 ELSE 0 END), 0) AS overdue_sales_count,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN s.balance_due ELSE 0 END), 0) AS overdue_total,
                COALESCE(MAX(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN CAST(julianday('now') - julianday(s.due_date) AS INTEGER) ELSE 0 END), 0) AS max_days_overdue
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id
            WHERE c.id = ?
            GROUP BY c.id, c.name, c.alert_limit
        ",
            params![payload.customer_id],
            |row| {
                let debt_total: f64 = row.get(3)?;
                let alert_limit: f64 = row.get(2)?;
                Ok(CustomerSummary {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    debt_total,
                    alert_limit,
                    over_limit: debt_total >= alert_limit,
                    overdue_sales_count: row.get(4)?,
                    overdue_total: row.get(5)?,
                    max_days_overdue: row.get(6)?,
                })
            },
        )
        .map_err(|e| db_error("No se pudo leer cliente actualizado", e))?;

    Ok(result)
}

#[tauri::command]
fn customer_account_snapshot(
    app: AppHandle,
    customer_id: i64,
    sales_limit: Option<i64>,
    payments_limit: Option<i64>,
) -> Result<CustomerAccountSnapshotResponse, String> {
    if customer_id <= 0 {
        return Err("Cliente invalido".to_string());
    }

    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let safe_sales_limit = sales_limit.unwrap_or(30).clamp(1, 120);
    let safe_payments_limit = payments_limit.unwrap_or(40).clamp(1, 200);

    let customer = conn
        .query_row(
            "
            SELECT
                c.id, c.name, c.phone, c.email, c.alert_limit, c.notes,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 THEN s.balance_due ELSE 0 END), 0) AS debt_total,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN 1 ELSE 0 END), 0) AS overdue_sales_count,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 AND s.due_date IS NOT NULL AND date(s.due_date) < date('now') THEN s.balance_due ELSE 0 END), 0) AS overdue_total
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id
            WHERE c.id = ?
            GROUP BY c.id, c.name, c.phone, c.email, c.alert_limit, c.notes
        ",
            params![customer_id],
            |row| {
                let debt_total: f64 = row.get(6)?;
                let alert_limit: f64 = row.get(4)?;
                Ok(CustomerAccountInfo {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    phone: row.get(2)?,
                    email: row.get(3)?,
                    alert_limit,
                    notes: row.get(5)?,
                    debt_total,
                    over_limit: debt_total >= alert_limit,
                    overdue_sales_count: row.get(7)?,
                    overdue_total: row.get(8)?,
                })
            },
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar cliente", e))?
        .ok_or_else(|| "Cliente no encontrado".to_string())?;

    let mut debt_sales: Vec<CustomerSaleItem> = Vec::new();
    let mut debt_stmt = conn
        .prepare(
            "
            SELECT
                id, sold_at, total, paid_amount, balance_due, due_date,
                COALESCE(CASE WHEN due_date IS NOT NULL AND date(due_date) < date('now') THEN CAST(julianday('now') - julianday(due_date) AS INTEGER) ELSE 0 END, 0),
                payment_method, status
            FROM sales
            WHERE customer_id = ? AND balance_due > 0
            ORDER BY sold_at ASC, id ASC
            LIMIT ?
        ",
        )
        .map_err(|e| db_error("No se pudo preparar deudas del cliente", e))?;
    let debt_rows = debt_stmt
        .query_map(params![customer_id, safe_sales_limit], |row| {
            Ok(CustomerSaleItem {
                sale_id: row.get(0)?,
                sold_at: row.get(1)?,
                total: row.get(2)?,
                paid_amount: row.get(3)?,
                balance_due: row.get(4)?,
                due_date: row.get(5)?,
                overdue_days: row.get(6)?,
                payment_method: row.get(7)?,
                status: row.get(8)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar deudas del cliente", e))?;
    for row in debt_rows {
        debt_sales.push(row.map_err(|e| db_error("No se pudo mapear deuda de cliente", e))?);
    }

    let mut recent_sales: Vec<CustomerSaleItem> = Vec::new();
    let mut sales_stmt = conn
        .prepare(
            "
            SELECT
                id, sold_at, total, paid_amount, balance_due, due_date,
                COALESCE(CASE WHEN due_date IS NOT NULL AND date(due_date) < date('now') THEN CAST(julianday('now') - julianday(due_date) AS INTEGER) ELSE 0 END, 0),
                payment_method, status
            FROM sales
            WHERE customer_id = ?
            ORDER BY sold_at DESC, id DESC
            LIMIT ?
        ",
        )
        .map_err(|e| db_error("No se pudo preparar historial de ventas de cliente", e))?;
    let sales_rows = sales_stmt
        .query_map(params![customer_id, safe_sales_limit], |row| {
            Ok(CustomerSaleItem {
                sale_id: row.get(0)?,
                sold_at: row.get(1)?,
                total: row.get(2)?,
                paid_amount: row.get(3)?,
                balance_due: row.get(4)?,
                due_date: row.get(5)?,
                overdue_days: row.get(6)?,
                payment_method: row.get(7)?,
                status: row.get(8)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar historial de ventas de cliente", e))?;
    for row in sales_rows {
        recent_sales.push(row.map_err(|e| db_error("No se pudo mapear venta de cliente", e))?);
    }

    let mut recent_payments: Vec<CustomerPaymentItem> = Vec::new();
    let mut payments_stmt = conn
        .prepare(
            "
            SELECT id, sale_id, paid_at, amount, payment_method, note
            FROM payments
            WHERE customer_id = ?
            ORDER BY paid_at DESC, id DESC
            LIMIT ?
        ",
        )
        .map_err(|e| db_error("No se pudo preparar historial de pagos de cliente", e))?;
    let payment_rows = payments_stmt
        .query_map(params![customer_id, safe_payments_limit], |row| {
            Ok(CustomerPaymentItem {
                id: row.get(0)?,
                sale_id: row.get(1)?,
                paid_at: row.get(2)?,
                amount: row.get(3)?,
                payment_method: row.get(4)?,
                note: row.get(5)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar historial de pagos de cliente", e))?;
    for row in payment_rows {
        recent_payments.push(row.map_err(|e| db_error("No se pudo mapear pago de cliente", e))?);
    }

    Ok(CustomerAccountSnapshotResponse {
        customer,
        debt_sales,
        recent_sales,
        recent_payments,
    })
}

#[tauri::command]
fn register_customer_payment(
    app: AppHandle,
    payload: RegisterCustomerPaymentRequest,
) -> Result<RegisterCustomerPaymentResponse, String> {
    if payload.customer_id <= 0 {
        return Err("Cliente invalido".to_string());
    }
    let amount = round_integer(payload.amount);
    if amount <= 0.0 {
        return Err("El monto debe ser mayor a cero".to_string());
    }

    let method = normalize_payment_method(&payload.payment_method)?;
    if method == "Deuda" || method == "Consumo interno" {
        return Err("Metodo de pago invalido para abono".to_string());
    }

    let mut conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de pago de cliente", e))?;

    let active: Option<i64> = tx
        .query_row(
            "SELECT active FROM customers WHERE id = ?",
            params![payload.customer_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| db_error("No se pudo validar cliente", e))?;
    match active {
        Some(1) => {}
        Some(_) => return Err("El cliente esta inactivo".to_string()),
        None => return Err("Cliente no encontrado".to_string()),
    }

    let debt_total_before: f64 = round_non_negative_integer(
        tx
        .query_row(
            "
            SELECT COALESCE(SUM(CASE WHEN balance_due > 0 THEN balance_due ELSE 0 END), 0)
            FROM sales
            WHERE customer_id = ?
        ",
            params![payload.customer_id],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo calcular deuda actual del cliente", e))?,
    );
    if debt_total_before <= 1e-9 {
        return Err("El cliente no tiene deuda pendiente".to_string());
    }
    if amount - debt_total_before > 1e-9 {
        return Err("El monto del abono supera la deuda pendiente".to_string());
    }

    let mut remaining = amount;
    let mut affected_sales = 0_i64;
    let clean_note = payload.note.unwrap_or_default().trim().to_string();

    {
        let mut sales_stmt = tx
            .prepare(
                "
                SELECT id, balance_due
                FROM sales
                WHERE customer_id = ? AND balance_due > 0
                ORDER BY sold_at ASC, id ASC
            ",
            )
            .map_err(|e| db_error("No se pudo preparar deudas para aplicar pago", e))?;
        let debt_rows = sales_stmt
            .query_map(params![payload.customer_id], |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, f64>(1)?))
            })
            .map_err(|e| db_error("No se pudieron listar deudas para aplicar pago", e))?;

        for debt_row in debt_rows {
            if remaining <= 1e-9 {
                break;
            }
            let (sale_id, balance_due_raw) =
                debt_row.map_err(|e| db_error("No se pudo mapear deuda para aplicar pago", e))?;
            let balance_due = round_non_negative_integer(balance_due_raw);
            let applied = remaining.min(balance_due);
            if applied <= 1e-9 {
                continue;
            }

            let next_balance = round_non_negative_integer(balance_due - applied);
            let next_status = if next_balance <= 1e-9 {
                "paid".to_string()
            } else {
                "partial".to_string()
            };

            tx.execute(
                "
                UPDATE sales
                SET paid_amount = ROUND(paid_amount + ?, 0), balance_due = ?, status = ?
                WHERE id = ?
            ",
                params![applied, next_balance, next_status, sale_id],
            )
            .map_err(|e| db_error("No se pudo actualizar deuda de venta", e))?;

            tx.execute(
                "
                INSERT INTO payments(
                    sale_id, customer_id, amount, payment_method, note,
                    reference_type, reference_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ",
                params![
                    sale_id,
                    payload.customer_id,
                    applied,
                    method,
                    if clean_note.is_empty() {
                        None::<String>
                    } else {
                        Some(clean_note.clone())
                    },
                    "customer_payment",
                    sale_id
                ],
            )
            .map_err(|e| db_error("No se pudo registrar abono del cliente", e))?;

            remaining -= applied;
            remaining = round_non_negative_integer(remaining);
            affected_sales += 1;
        }
    }

    let applied_total = round_non_negative_integer(amount - remaining.max(0.0));
    if applied_total <= 1e-9 {
        return Err("No se pudo aplicar el abono a deudas pendientes".to_string());
    }

    let debt_total_after: f64 = round_non_negative_integer(
        tx
        .query_row(
            "
            SELECT COALESCE(SUM(CASE WHEN balance_due > 0 THEN balance_due ELSE 0 END), 0)
            FROM sales
            WHERE customer_id = ?
        ",
            params![payload.customer_id],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo calcular deuda final del cliente", e))?,
    );

    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar pago de cliente", e))?;

    Ok(RegisterCustomerPaymentResponse {
        customer_id: payload.customer_id,
        applied_total,
        debt_total_before,
        debt_total_after,
        affected_sales,
    })
}

#[tauri::command]
fn list_categories(app: AppHandle) -> Result<Vec<CategorySummary>, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let mut stmt = conn
        .prepare("SELECT id, name, margin_percent FROM categories ORDER BY name")
        .map_err(|e| db_error("No se pudo preparar consulta de categorias", e))?;
    let rows = stmt
        .query_map([], |row| {
            Ok(CategorySummary {
                id: row.get(0)?,
                name: row.get(1)?,
                margin_percent: row.get(2)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar categorias", e))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear categoria", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn list_categories_admin(app: AppHandle) -> Result<Vec<CategoryAdminSummary>, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let mut stmt = conn
        .prepare(
            "
            SELECT
                c.id, c.name, c.margin_percent,
                COALESCE(SUM(CASE WHEN p.active = 1 THEN 1 ELSE 0 END), 0) AS product_count
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id
            GROUP BY c.id, c.name, c.margin_percent
            ORDER BY c.name
        ",
        )
        .map_err(|e| db_error("No se pudo preparar listado admin de categorias", e))?;

    let rows = stmt
        .query_map([], |row| {
            Ok(CategoryAdminSummary {
                id: row.get(0)?,
                name: row.get(1)?,
                margin_percent: row.get(2)?,
                product_count: row.get(3)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar categorias admin", e))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear categoria admin", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn create_category(
    app: AppHandle,
    payload: CreateCategoryRequest,
) -> Result<CategoryAdminSummary, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let clean_name = payload.name.trim().to_string();
    if clean_name.is_empty() {
        return Err("El nombre de categoria es obligatorio".to_string());
    }
    if payload.margin_percent < 0.0 {
        return Err("El margen no puede ser negativo".to_string());
    }

    conn.execute(
        "INSERT INTO categories(name, margin_percent) VALUES (?, ?)",
        params![clean_name, payload.margin_percent],
    )
    .map_err(|e| {
        db_error(
            "No se pudo crear categoria (nombre duplicado o datos invalidos)",
            e,
        )
    })?;

    let category_id = conn.last_insert_rowid();
    read_category_admin(&conn, category_id)
}

#[tauri::command]
fn update_category(
    app: AppHandle,
    payload: UpdateCategoryRequest,
) -> Result<CategoryAdminSummary, String> {
    if payload.id <= 0 {
        return Err("Categoria invalida".to_string());
    }

    let clean_name = payload.name.trim().to_string();
    if clean_name.is_empty() {
        return Err("El nombre de categoria es obligatorio".to_string());
    }
    if payload.margin_percent < 0.0 {
        return Err("El margen no puede ser negativo".to_string());
    }

    let mut conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let rounding_base = get_rounding_base(&conn);
    let base = if rounding_base <= 0 {
        100.0
    } else {
        rounding_base as f64
    };

    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de categoria", e))?;

    let affected = tx
        .execute(
            "UPDATE categories SET name = ?, margin_percent = ? WHERE id = ?",
            params![clean_name, payload.margin_percent, payload.id],
        )
        .map_err(|e| {
            db_error(
                "No se pudo actualizar categoria (nombre duplicado o datos invalidos)",
                e,
            )
        })?;
    if affected == 0 {
        return Err("Categoria no encontrada".to_string());
    }

    tx.execute(
        "
        UPDATE products
        SET sale_price = ROUND((cost + (cost * (? / 100.0))) / ?) * ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE category_id = ? AND auto_price = 1
    ",
        params![payload.margin_percent, base, base, payload.id],
    )
    .map_err(|e| {
        db_error(
            "No se pudo recalcular precios automaticos de la categoria",
            e,
        )
    })?;

    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar actualizacion de categoria", e))?;

    read_category_admin(&conn, payload.id)
}

#[tauri::command]
fn delete_category(app: AppHandle, category_id: i64) -> Result<CategoryDeleteResponse, String> {
    if category_id <= 0 {
        return Err("Categoria invalida".to_string());
    }

    let mut conn = open_db(&app)?;
    let admin = require_admin_user(&conn)?;
    let product_count: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM products WHERE category_id = ?",
            params![category_id],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo validar productos de la categoria", e))?;
    if product_count > 0 {
        return Err("No se puede eliminar una categoria con productos asociados".to_string());
    }

    let (category_name, margin_percent): (String, f64) = conn
        .query_row(
            "SELECT name, margin_percent FROM categories WHERE id = ? LIMIT 1",
            params![category_id],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar categoria para eliminar", e))?
        .ok_or_else(|| "Categoria no encontrada".to_string())?;

    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de categoria", e))?;

    tx.execute(
        "
        INSERT INTO deleted_category_archives(
            original_category_id, name, margin_percent, deleted_by_user_id
        ) VALUES (?, ?, ?, ?)
    ",
        params![category_id, category_name, margin_percent, admin.id],
    )
    .map_err(|e| db_error("No se pudo archivar categoria eliminada", e))?;

    let affected = tx
        .execute("DELETE FROM categories WHERE id = ?", params![category_id])
        .map_err(|e| db_error("No se pudo eliminar categoria", e))?;
    if affected == 0 {
        return Err("Categoria no encontrada".to_string());
    }

    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar eliminacion de categoria", e))?;

    Ok(CategoryDeleteResponse { id: category_id })
}

#[tauri::command]
fn list_deleted_categories(app: AppHandle) -> Result<Vec<DeletedCategoryArchiveRow>, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;

    let mut stmt = conn
        .prepare(
            "
            SELECT id, original_category_id, name, margin_percent, deleted_at
            FROM deleted_category_archives
            ORDER BY deleted_at DESC, id DESC
        ",
        )
        .map_err(|e| db_error("No se pudo preparar categorias eliminadas", e))?;

    let rows = stmt
        .query_map([], |row| {
            Ok(DeletedCategoryArchiveRow {
                archive_id: row.get(0)?,
                original_category_id: row.get(1)?,
                name: row.get(2)?,
                margin_percent: row.get(3)?,
                deleted_at: row.get(4)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar categorias eliminadas", e))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear categoria eliminada", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn restore_deleted_category(
    app: AppHandle,
    payload: RestoreDeletedCategoryRequest,
) -> Result<RestoreDeletedCategoryResponse, String> {
    if payload.archive_id <= 0 {
        return Err("Registro de categoria eliminado invalido".to_string());
    }

    let mut conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion para restaurar categoria", e))?;

    let (archive_id, category_name, margin_percent): (i64, String, f64) = tx
        .query_row(
            "
            SELECT id, name, margin_percent
            FROM deleted_category_archives
            WHERE id = ?
            LIMIT 1
        ",
            params![payload.archive_id],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar categoria eliminada", e))?
        .ok_or_else(|| "Registro de categoria eliminada no encontrado".to_string())?;

    tx.execute(
        "INSERT INTO categories(name, margin_percent) VALUES (?, ?)",
        params![category_name, margin_percent],
    )
    .map_err(|e| {
        db_error(
            "No se pudo restaurar categoria (puede existir otra con el mismo nombre)",
            e,
        )
    })?;
    let new_category_id = tx.last_insert_rowid();

    tx.execute(
        "DELETE FROM deleted_category_archives WHERE id = ?",
        params![archive_id],
    )
    .map_err(|e| db_error("No se pudo limpiar archivo de categoria restaurada", e))?;

    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar restauracion de categoria", e))?;

    Ok(RestoreDeletedCategoryResponse {
        archive_id,
        category: read_category_admin(&conn, new_category_id)?,
    })
}

#[tauri::command]
fn list_products_admin(
    app: AppHandle,
    search: Option<String>,
    category_id: Option<i64>,
    include_inactive: Option<bool>,
    limit: Option<i64>,
) -> Result<Vec<ProductAdminRow>, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let safe_limit = limit.unwrap_or(180).clamp(1, 1200);
    let clean_search = search.unwrap_or_default().trim().to_string();
    let like = format!("%{clean_search}%");
    let show_inactive = if include_inactive.unwrap_or(false) {
        1_i64
    } else {
        0_i64
    };

    let mut stmt = conn
        .prepare(
            "
            SELECT
                p.id, p.name, p.barcode, p.category_id, c.name,
                p.cost, p.sale_price, p.auto_price, p.stock, p.min_stock, p.active
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE (? = '' OR p.name LIKE ? OR p.barcode LIKE ?)
              AND (? IS NULL OR p.category_id = ?)
              AND (? = 1 OR p.active = 1)
            ORDER BY p.name
            LIMIT ?
        ",
        )
        .map_err(|e| db_error("No se pudo preparar listado admin de productos", e))?;

    let rows = stmt
        .query_map(
            params![
                &clean_search,
                &like,
                &like,
                category_id,
                category_id,
                show_inactive,
                safe_limit
            ],
            |row| {
                Ok(ProductAdminRow {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    barcode: row.get(2)?,
                    category_id: row.get(3)?,
                    category_name: row.get(4)?,
                    cost: row.get(5)?,
                    sale_price: row.get(6)?,
                    auto_price: row.get::<_, i64>(7)? == 1,
                    stock: row.get(8)?,
                    min_stock: row.get(9)?,
                    active: row.get::<_, i64>(10)? == 1,
                })
            },
        )
        .map_err(|e| db_error("No se pudo listar productos admin", e))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear producto admin", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn create_product(app: AppHandle, payload: CreateProductRequest) -> Result<ProductSummary, String> {
    let mut conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;

    let clean_name = payload.name.trim().to_string();
    let clean_barcode = payload.barcode.trim().to_string();
    if clean_name.is_empty() {
        return Err("El nombre del producto es obligatorio".to_string());
    }
    if payload.cost <= 0.0 {
        return Err("El costo inicial debe ser mayor a cero".to_string());
    }
    if payload.stock <= 0.0 {
        return Err("El stock inicial debe ser mayor a cero".to_string());
    }
    if payload.min_stock < 0.0 {
        return Err("El stock minimo no puede ser negativo".to_string());
    }
    let cost = round_integer(payload.cost);
    let stock = round_integer(payload.stock);
    let min_stock = round_integer(payload.min_stock);
    let manual_sale_price = round_integer(payload.sale_price);

    let margin_percent: f64 = conn
        .query_row(
            "SELECT margin_percent FROM categories WHERE id = ?",
            params![payload.category_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar categoria", e))?
        .ok_or_else(|| "Categoria no encontrada".to_string())?;

    let rounding_base = get_rounding_base(&conn);
    let final_sale_price = if payload.auto_price {
        round_integer(calculate_auto_price(cost, margin_percent, rounding_base))
    } else {
        manual_sale_price
    };
    if final_sale_price < 0.0 {
        return Err("El precio de venta no puede ser negativo".to_string());
    }

    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de producto", e))?;
    let insert_result = tx.execute(
        "
        INSERT INTO products(
            name, barcode, category_id, cost, sale_price,
            auto_price, stock, min_stock, active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    ",
        params![
            clean_name,
            if clean_barcode.is_empty() {
                None::<String>
            } else {
                Some(clean_barcode.clone())
            },
            payload.category_id,
            cost,
            final_sale_price,
            if payload.auto_price { 1 } else { 0 },
            stock,
            min_stock
        ],
    );

    if let Err(e) = insert_result {
        return Err(db_error(
            "No se pudo crear producto (codigo de barras duplicado o datos invalidos)",
            e,
        ));
    }
    let product_id = tx.last_insert_rowid();
    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar creacion de producto", e))?;

    let created = conn
        .query_row(
            "
            SELECT id, name, barcode, sale_price, stock
            FROM products
            WHERE id = ?
        ",
            params![product_id],
            |row| {
                Ok(ProductSummary {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    barcode: row.get(2)?,
                    sale_price: row.get(3)?,
                    stock: row.get(4)?,
                })
            },
        )
        .map_err(|e| db_error("No se pudo leer producto creado", e))?;

    Ok(created)
}

#[tauri::command]
fn update_product(
    app: AppHandle,
    payload: UpdateProductRequest,
) -> Result<ProductAdminRow, String> {
    if payload.id <= 0 {
        return Err("Producto invalido".to_string());
    }

    let clean_name = payload.name.trim().to_string();
    let clean_barcode = payload.barcode.trim().to_string();
    if clean_name.is_empty() {
        return Err("El nombre del producto es obligatorio".to_string());
    }
    if payload.cost < 0.0 {
        return Err("El costo no puede ser negativo".to_string());
    }
    if payload.stock < 0.0 {
        return Err("El stock no puede ser negativo".to_string());
    }
    if payload.min_stock < 0.0 {
        return Err("El stock minimo no puede ser negativo".to_string());
    }
    let cost = round_integer(payload.cost);
    let stock = round_integer(payload.stock);
    let min_stock = round_integer(payload.min_stock);
    let manual_sale_price = round_integer(payload.sale_price);

    let mut conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let margin_percent: f64 = conn
        .query_row(
            "SELECT margin_percent FROM categories WHERE id = ?",
            params![payload.category_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar categoria del producto", e))?
        .ok_or_else(|| "Categoria no encontrada".to_string())?;

    let rounding_base = get_rounding_base(&conn);
    let final_sale_price = if payload.auto_price {
        round_integer(calculate_auto_price(cost, margin_percent, rounding_base))
    } else {
        manual_sale_price
    };
    if final_sale_price < 0.0 {
        return Err("El precio de venta no puede ser negativo".to_string());
    }

    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de producto", e))?;
    let update_result = tx.execute(
        "
        UPDATE products
        SET
            name = ?,
            barcode = ?,
            category_id = ?,
            cost = ?,
            sale_price = ?,
            auto_price = ?,
            stock = ?,
            min_stock = ?,
            active = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ",
        params![
            clean_name,
            if clean_barcode.is_empty() {
                None::<String>
            } else {
                Some(clean_barcode.clone())
            },
            payload.category_id,
            cost,
            final_sale_price,
            if payload.auto_price { 1 } else { 0 },
            stock,
            min_stock,
            if payload.active { 1 } else { 0 },
            payload.id
        ],
    );

    let affected = match update_result {
        Ok(value) => value,
        Err(e) => {
            return Err(db_error(
                "No se pudo actualizar producto (codigo de barras duplicado o datos invalidos)",
                e,
            ))
        }
    };
    if affected == 0 {
        return Err("Producto no encontrado".to_string());
    }

    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar actualizacion de producto", e))?;

    read_product_admin(&conn, payload.id)
}

#[tauri::command]
fn inventory_list_movements(
    app: AppHandle,
    search: Option<String>,
    movement_type: Option<String>,
    limit: Option<i64>,
) -> Result<Vec<InventoryMovementRow>, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let safe_limit = limit.unwrap_or(250).clamp(1, 1200);
    let clean_search = search.unwrap_or_default().trim().to_string();
    let like = format!("%{clean_search}%");

    let movement_filter = movement_type
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(normalize_inventory_movement_filter_type)
        .transpose()?;

    let mut stmt = conn
        .prepare(
            "
            SELECT
                m.id, m.created_at, m.movement_type, m.quantity,
                m.stock_before, m.stock_after, p.id, p.name, p.barcode, m.note,
                m.reference_type, m.reference_id
            FROM stock_movements m
            JOIN products p ON p.id = m.product_id
            WHERE (? = '' OR p.name LIKE ? OR p.barcode LIKE ?)
              AND (? IS NULL OR m.movement_type = ?)
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
        ",
        )
        .map_err(|e| db_error("No se pudo preparar consulta de inventario", e))?;

    let rows = stmt
        .query_map(
            params![
                &clean_search,
                &like,
                &like,
                movement_filter.as_deref(),
                movement_filter.as_deref(),
                safe_limit
            ],
            |row| {
                Ok(InventoryMovementRow {
                    id: row.get(0)?,
                    created_at: row.get(1)?,
                    movement_type: row.get(2)?,
                    quantity: row.get(3)?,
                    stock_before: row.get(4)?,
                    stock_after: row.get(5)?,
                    product_id: row.get(6)?,
                    product_name: row.get(7)?,
                    barcode: row.get(8)?,
                    note: row.get(9)?,
                    reference_type: row.get(10)?,
                    reference_id: row.get(11)?,
                })
            },
        )
        .map_err(|e| db_error("No se pudo listar movimientos de inventario", e))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear movimiento de inventario", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn register_inventory_movement(
    app: AppHandle,
    payload: RegisterInventoryMovementRequest,
) -> Result<RegisterInventoryMovementResponse, String> {
    if payload.product_id <= 0 {
        return Err("Producto invalido".to_string());
    }

    let movement_type = normalize_inventory_movement_type(&payload.movement_type)?;
    let note_text = payload.note.unwrap_or_default().trim().to_string();
    let mut conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;

    let (product_id, product_name, barcode, sale_price, stock_before, unit_cost) = conn
        .query_row(
            "
            SELECT id, name, barcode, sale_price, stock, cost
            FROM products
            WHERE id = ?
            LIMIT 1
        ",
            params![payload.product_id],
            |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, Option<String>>(2)?,
                    round_integer(row.get::<_, f64>(3)?),
                    round_integer(row.get::<_, f64>(4)?),
                    round_integer(row.get::<_, f64>(5)?),
                ))
            },
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar producto para inventario", e))?
        .ok_or_else(|| "Producto no encontrado".to_string())?;

    let (quantity_delta, stock_after, message) = match movement_type.as_str() {
        "manual_in" => {
            let quantity = round_integer(payload.quantity.unwrap_or(0.0));
            if quantity <= 0.0 {
                return Err("La cantidad de entrada debe ser mayor a cero".to_string());
            }
            (
                quantity,
                round_integer(stock_before + quantity),
                "Entrada de inventario registrada".to_string(),
            )
        }
        "manual_out" => {
            let quantity = round_integer(payload.quantity.unwrap_or(0.0));
            if quantity <= 0.0 {
                return Err("La cantidad de salida debe ser mayor a cero".to_string());
            }
            let next_stock = round_integer(stock_before - quantity);
            if next_stock < 0.0 {
                return Err("La salida no puede dejar stock negativo".to_string());
            }
            (
                -quantity,
                next_stock,
                "Salida de inventario registrada".to_string(),
            )
        }
        "adjustment" => {
            let target = round_integer(
                payload
                .stock_target
                .ok_or_else(|| "Debes indicar stock objetivo para ajuste".to_string())?,
            );
            if target < 0.0 {
                return Err("El stock objetivo no puede ser negativo".to_string());
            }
            let delta = round_integer(target - stock_before);
            if delta.abs() <= 1e-9 {
                return Err("El ajuste no genera cambios de stock".to_string());
            }
            (delta, target, "Ajuste de inventario registrado".to_string())
        }
        _ => return Err("Tipo de movimiento invalido".to_string()),
    };

    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de inventario", e))?;
    tx.execute(
        "
        UPDATE products
        SET stock = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ",
        params![stock_after, product_id],
    )
    .map_err(|e| db_error("No se pudo actualizar stock del producto", e))?;

    tx.execute(
        "
        INSERT INTO stock_movements(
            product_id, movement_type, quantity, stock_before,
            stock_after, unit_cost, reference_type, reference_id, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ",
        params![
            product_id,
            movement_type,
            quantity_delta,
            stock_before,
            stock_after,
            unit_cost,
            "manual",
            Option::<i64>::None,
            if note_text.is_empty() {
                None::<String>
            } else {
                Some(note_text.clone())
            }
        ],
    )
    .map_err(|e| db_error("No se pudo registrar movimiento de inventario", e))?;
    let movement_id = tx.last_insert_rowid();
    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar movimiento de inventario", e))?;

    let created_at: String = conn
        .query_row(
            "SELECT created_at FROM stock_movements WHERE id = ?",
            params![movement_id],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo leer movimiento de inventario creado", e))?;

    Ok(RegisterInventoryMovementResponse {
        message,
        product: ProductSummary {
            id: product_id,
            name: product_name.clone(),
            barcode: barcode.clone(),
            sale_price,
            stock: stock_after,
        },
        movement: InventoryMovementRow {
            id: movement_id,
            created_at,
            movement_type,
            quantity: quantity_delta,
            stock_before,
            stock_after,
            product_id,
            product_name,
            barcode,
            note: if note_text.is_empty() {
                None::<String>
            } else {
                Some(note_text)
            },
            reference_type: Some("manual".to_string()),
            reference_id: None,
        },
    })
}

#[tauri::command]
fn reverse_stock_movement(
    app: AppHandle,
    payload: ReverseStockMovementRequest,
) -> Result<ReverseStockMovementResponse, String> {
    if payload.movement_id <= 0 {
        return Err("Movimiento invalido".to_string());
    }

    let mut conn = open_db(&app)?;
    let admin = require_admin_user(&conn)?;
    let reason_text = payload.reason.unwrap_or_default().trim().to_string();
    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de reversion", e))?;

    let already_reversed: Option<i64> = tx
        .query_row(
            "SELECT reversal_movement_id FROM stock_movement_reversals WHERE movement_id = ? LIMIT 1",
            params![payload.movement_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| db_error("No se pudo validar estado de reversion de movimiento", e))?;
    if already_reversed.is_some() {
        return Err("Ese movimiento ya fue revertido".to_string());
    }

    let (
        movement_id,
        product_id,
        movement_type,
        quantity,
        unit_cost,
        reference_type,
        product_name,
        barcode,
        sale_price,
        current_stock,
    ): (i64, i64, String, f64, f64, Option<String>, String, Option<String>, f64, f64) = tx
        .query_row(
            "
            SELECT
                m.id, m.product_id, m.movement_type, m.quantity,
                COALESCE(m.unit_cost, p.cost), m.reference_type,
                p.name, p.barcode, p.sale_price, p.stock
            FROM stock_movements m
            JOIN products p ON p.id = m.product_id
            WHERE m.id = ?
            LIMIT 1
        ",
            params![payload.movement_id],
            |row| {
                Ok((
                    row.get(0)?,
                    row.get(1)?,
                    row.get(2)?,
                    round_integer(row.get::<_, f64>(3)?),
                    round_integer(row.get::<_, f64>(4)?),
                    row.get(5)?,
                    row.get(6)?,
                    row.get(7)?,
                    round_integer(row.get::<_, f64>(8)?),
                    round_integer(row.get::<_, f64>(9)?),
                ))
            },
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar movimiento para revertir", e))?
        .ok_or_else(|| "Movimiento no encontrado".to_string())?;

    if !matches!(movement_type.as_str(), "manual_in" | "manual_out" | "adjustment") {
        return Err("Solo se pueden revertir movimientos manuales o ajustes".to_string());
    }

    if let Some(reference) = reference_type.as_deref() {
        if reference == "sale" || reference == "internal_consumption" {
            return Err(
                "Este movimiento proviene de una venta. Reverti la venta completa.".to_string(),
            );
        }
        if reference == "sale_reversal" || reference == "stock_reversal" {
            return Err("No se puede revertir una reversion previa".to_string());
        }
    }

    let quantity_reverted = round_integer(-quantity);
    if quantity_reverted.abs() <= 1e-9 {
        return Err("Movimiento sin cantidad para revertir".to_string());
    }
    let stock_after = round_integer(current_stock + quantity_reverted);
    if stock_after < 0.0 {
        return Err("No se puede revertir porque el stock quedaria negativo".to_string());
    }
    let reversal_type = if quantity_reverted >= 0.0 {
        "manual_in".to_string()
    } else {
        "manual_out".to_string()
    };
    let reversal_note = if reason_text.is_empty() {
        format!("Reversion movimiento #{movement_id}")
    } else {
        format!("Reversion movimiento #{movement_id}: {reason_text}")
    };

    tx.execute(
        "
        UPDATE products
        SET stock = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ",
        params![stock_after, product_id],
    )
    .map_err(|e| db_error("No se pudo actualizar stock al revertir movimiento", e))?;

    tx.execute(
        "
        INSERT INTO stock_movements(
            product_id, movement_type, quantity, stock_before,
            stock_after, unit_cost, reference_type, reference_id, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ",
        params![
            product_id,
            reversal_type,
            quantity_reverted,
            current_stock,
            stock_after,
            unit_cost,
            "stock_reversal",
            movement_id,
            reversal_note
        ],
    )
    .map_err(|e| db_error("No se pudo registrar movimiento de reversion", e))?;
    let reversal_movement_id = tx.last_insert_rowid();

    tx.execute(
        "
        INSERT INTO stock_movement_reversals(
            movement_id, reversal_movement_id, product_id, reversed_by_user_id, reason
        ) VALUES (?, ?, ?, ?, ?)
    ",
        params![
            movement_id,
            reversal_movement_id,
            product_id,
            admin.id,
            if reason_text.is_empty() {
                None::<String>
            } else {
                Some(reason_text.clone())
            }
        ],
    )
    .map_err(|e| db_error("No se pudo guardar auditoria de reversion de movimiento", e))?;

    let reversed_at: String = tx
        .query_row(
            "SELECT reversed_at FROM stock_movement_reversals WHERE movement_id = ?",
            params![movement_id],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo leer fecha de reversion de movimiento", e))?;

    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar reversion de movimiento", e))?;

    Ok(ReverseStockMovementResponse {
        movement_id,
        reversal_movement_id,
        reversed_at,
        product: ProductSummary {
            id: product_id,
            name: product_name,
            barcode,
            sale_price,
            stock: stock_after,
        },
        quantity_reverted,
    })
}

#[tauri::command]
fn list_recent_stock_movements(
    app: AppHandle,
    limit: Option<i64>,
) -> Result<Vec<StockMovementSummary>, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let safe_limit = limit.unwrap_or(60).clamp(1, 500);
    let mut stmt = conn
        .prepare(
            "
            SELECT
                m.id, m.created_at, m.movement_type, m.quantity,
                m.stock_before, m.stock_after, p.name, p.barcode, m.reference_type, m.reference_id
            FROM stock_movements m
            JOIN products p ON p.id = m.product_id
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
        ",
        )
        .map_err(|e| db_error("No se pudo preparar consulta de movimientos", e))?;

    let rows = stmt
        .query_map(params![safe_limit], |row| {
            Ok(StockMovementSummary {
                id: row.get(0)?,
                created_at: row.get(1)?,
                movement_type: row.get(2)?,
                quantity: row.get(3)?,
                stock_before: row.get(4)?,
                stock_after: row.get(5)?,
                product_name: row.get(6)?,
                barcode: row.get(7)?,
                reference_type: row.get(8)?,
                reference_id: row.get(9)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar movimientos", e))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear movimiento", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn quick_stock_lookup_by_barcode(
    app: AppHandle,
    barcode: String,
) -> Result<QuickStockLookupResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let clean_barcode = barcode.trim().to_string();
    if clean_barcode.is_empty() {
        return Err("Escanea o ingresa un codigo de barras".to_string());
    }

    let maybe_product = conn
        .query_row(
            "
            SELECT id, name, barcode, stock, cost, sale_price
            FROM products
            WHERE active = 1 AND barcode = ?
            LIMIT 1
        ",
            params![clean_barcode],
            |row| {
                Ok(QuickStockLookupProduct {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    barcode: row.get(2)?,
                    stock: round_integer(row.get::<_, f64>(3)?),
                    cost: round_integer(row.get::<_, f64>(4)?),
                    sale_price: round_integer(row.get::<_, f64>(5)?),
                })
            },
        )
        .optional()
        .map_err(|e| db_error("No se pudo buscar producto para stock", e))?;

    match maybe_product {
        Some(product) => Ok(QuickStockLookupResponse {
            found: true,
            message: "Producto encontrado. Confirma cantidad y costo para agregar stock."
                .to_string(),
            product: Some(product),
        }),
        None => Ok(QuickStockLookupResponse {
            found: false,
            message: "Producto no encontrado. Crea el producto completo.".to_string(),
            product: None,
        }),
    }
}

#[tauri::command]
fn quick_stock_add_by_barcode(
    app: AppHandle,
    payload: QuickStockAddRequest,
) -> Result<QuickStockAddResponse, String> {
    let mut conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let clean_barcode = payload.barcode.trim().to_string();
    let quantity = round_integer(payload.quantity);
    if clean_barcode.is_empty() {
        return Err("Escanea o ingresa un codigo de barras".to_string());
    }
    if quantity <= 0.0 {
        return Err("La cantidad debe ser mayor a cero".to_string());
    }

    let maybe_product = conn
        .query_row(
            "
            SELECT
                p.id, p.name, p.barcode, p.sale_price, p.stock, p.cost, p.auto_price, c.margin_percent
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.active = 1 AND p.barcode = ?
            LIMIT 1
        ",
            params![clean_barcode],
            |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, Option<String>>(2)?,
                    round_integer(row.get::<_, f64>(3)?),
                    round_integer(row.get::<_, f64>(4)?),
                    round_integer(row.get::<_, f64>(5)?),
                    row.get::<_, i64>(6)?,
                    row.get::<_, f64>(7)?,
                ))
            },
        )
        .optional()
        .map_err(|e| db_error("No se pudo buscar producto para stock", e))?;

    let Some((
        product_id,
        product_name,
        barcode,
        current_sale_price,
        stock_before,
        current_cost,
        auto_price_raw,
        category_margin_percent,
    )) = maybe_product
    else {
        return Ok(QuickStockAddResponse {
            found: false,
            message: "Producto no encontrado. Crea el producto completo.".to_string(),
            product: None,
            movement_id: None,
        });
    };

    let entered_cost = payload.unit_cost.map(round_integer);
    if let Some(cost_value) = entered_cost {
        if cost_value <= 0.0 {
            return Err("El costo debe ser mayor a cero".to_string());
        }
    }
    let next_cost = entered_cost.unwrap_or(current_cost);
    let auto_price_enabled = auto_price_raw == 1;
    let next_sale_price = if entered_cost.is_some() && auto_price_enabled {
        let rounding_base = get_rounding_base(&conn);
        round_integer(calculate_auto_price(
            next_cost,
            category_margin_percent,
            rounding_base,
        ))
    } else {
        current_sale_price
    };

    let stock_after = round_integer(stock_before + quantity);
    let note_text = payload.note.unwrap_or_default().trim().to_string();

    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de stock", e))?;
    tx.execute(
        "
        UPDATE products
        SET stock = ?, cost = ?, sale_price = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ",
        params![stock_after, next_cost, next_sale_price, product_id],
    )
    .map_err(|e| db_error("No se pudo actualizar stock", e))?;

    tx.execute(
        "
        INSERT INTO stock_movements(
            product_id, movement_type, quantity, stock_before,
            stock_after, unit_cost, reference_type, reference_id, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ",
        params![
            product_id,
            "manual_in",
            quantity,
            stock_before,
            stock_after,
            next_cost,
            "manual",
            Option::<i64>::None,
            if note_text.is_empty() {
                None::<String>
            } else {
                Some(note_text)
            }
        ],
    )
    .map_err(|e| db_error("No se pudo registrar movimiento de stock", e))?;
    let movement_id = tx.last_insert_rowid();
    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar movimiento de stock", e))?;

    Ok(QuickStockAddResponse {
        found: true,
        message: "Stock actualizado correctamente".to_string(),
        product: Some(ProductSummary {
            id: product_id,
            name: product_name,
            barcode,
            sale_price: next_sale_price,
            stock: stock_after,
        }),
        movement_id: Some(movement_id),
    })
}

#[tauri::command]
fn dashboard_snapshot(
    app: AppHandle,
    month: Option<String>,
) -> Result<DashboardSnapshotResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let month_key = resolve_month_key(month)?;

    let (
        gross_total,
        paid_total,
        due_total,
        sales_count,
        internal_consumption_total,
        internal_operations_count,
    ): (f64, f64, f64, i64, f64, i64) = conn
        .query_row(
            "
            SELECT
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') <> 'internal' THEN total ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') <> 'internal' THEN paid_amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') <> 'internal' THEN balance_due ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') <> 'internal' THEN 1 ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') = 'internal' THEN total ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN COALESCE(sale_type, 'cash') = 'internal' THEN 1 ELSE 0 END), 0)
            FROM sales
            WHERE substr(sold_at, 1, 7) = ?
        ",
            params![&month_key],
            |row| {
                Ok((
                    row.get(0)?,
                    row.get(1)?,
                    row.get(2)?,
                    row.get(3)?,
                    row.get(4)?,
                    row.get(5)?,
                ))
            },
        )
        .map_err(|e| db_error("No se pudo calcular resumen de ventas", e))?;

    let estimated_profit: f64 = conn
        .query_row(
            "
            SELECT COALESCE(SUM((si.unit_price - si.cost_at_sale) * si.quantity), 0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE substr(s.sold_at, 1, 7) = ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
        ",
            params![&month_key],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo calcular ganancia estimada", e))?;
    let net_profit_after_internal = round_integer(estimated_profit - internal_consumption_total);

    let mut payment_breakdown: Vec<PaymentBreakdownItem> = Vec::new();
    let mut payment_stmt = conn
        .prepare(
            "
            SELECT payment_method, COALESCE(SUM(paid_amount), 0)
            FROM sales
            WHERE substr(sold_at, 1, 7) = ? AND paid_amount > 0 AND COALESCE(sale_type, 'cash') <> 'internal'
            GROUP BY payment_method
            ORDER BY COALESCE(SUM(paid_amount), 0) DESC, payment_method ASC
        ",
        )
        .map_err(|e| db_error("No se pudo preparar resumen por metodo de pago", e))?;
    let payment_rows = payment_stmt
        .query_map(params![&month_key], |row| {
            Ok(PaymentBreakdownItem {
                payment_method: row.get(0)?,
                total: row.get(1)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar metodos de pago", e))?;
    for row in payment_rows {
        payment_breakdown.push(row.map_err(|e| db_error("No se pudo mapear metodo de pago", e))?);
    }

    let mut top_products: Vec<ProductRankingItem> = Vec::new();
    let mut top_stmt = conn
        .prepare(
            "
            SELECT
                si.product_name,
                COALESCE(SUM(si.quantity), 0),
                COALESCE(SUM(si.subtotal), 0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE substr(s.sold_at, 1, 7) = ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
            GROUP BY si.product_name
            HAVING COALESCE(SUM(si.quantity), 0) > 0
            ORDER BY COALESCE(SUM(si.quantity), 0) DESC, COALESCE(SUM(si.subtotal), 0) DESC
            LIMIT 8
        ",
        )
        .map_err(|e| db_error("No se pudo preparar top productos", e))?;
    let top_rows = top_stmt
        .query_map(params![&month_key], |row| {
            Ok(ProductRankingItem {
                product_name: row.get(0)?,
                quantity: row.get(1)?,
                revenue: row.get(2)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar top productos", e))?;
    for row in top_rows {
        top_products.push(row.map_err(|e| db_error("No se pudo mapear top productos", e))?);
    }

    let mut low_products: Vec<ProductRankingItem> = Vec::new();
    let mut low_stmt = conn
        .prepare(
            "
            SELECT
                si.product_name,
                COALESCE(SUM(si.quantity), 0),
                COALESCE(SUM(si.subtotal), 0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE substr(s.sold_at, 1, 7) = ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
            GROUP BY si.product_name
            HAVING COALESCE(SUM(si.quantity), 0) > 0
            ORDER BY COALESCE(SUM(si.quantity), 0) ASC, COALESCE(SUM(si.subtotal), 0) ASC
            LIMIT 8
        ",
        )
        .map_err(|e| db_error("No se pudo preparar productos con baja salida", e))?;
    let low_rows = low_stmt
        .query_map(params![&month_key], |row| {
            Ok(ProductRankingItem {
                product_name: row.get(0)?,
                quantity: row.get(1)?,
                revenue: row.get(2)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar productos con baja salida", e))?;
    for row in low_rows {
        low_products
            .push(row.map_err(|e| db_error("No se pudo mapear productos con baja salida", e))?);
    }

    let mut low_stock_alerts: Vec<LowStockAlertItem> = Vec::new();
    let mut low_stock_stmt = conn
        .prepare(
            "
            SELECT id, name, barcode, stock, min_stock
            FROM products
            WHERE active = 1 AND stock <= min_stock
            ORDER BY (min_stock - stock) DESC, name ASC
            LIMIT 20
        ",
        )
        .map_err(|e| db_error("No se pudo preparar alertas de stock bajo", e))?;
    let low_stock_rows = low_stock_stmt
        .query_map([], |row| {
            let stock: f64 = row.get(3)?;
            let min_stock: f64 = row.get(4)?;
            Ok(LowStockAlertItem {
                id: row.get(0)?,
                name: row.get(1)?,
                barcode: row.get(2)?,
                stock,
                min_stock,
                shortage: (min_stock - stock).max(0.0),
            })
        })
        .map_err(|e| db_error("No se pudo listar alertas de stock bajo", e))?;
    for row in low_stock_rows {
        low_stock_alerts.push(row.map_err(|e| db_error("No se pudo mapear stock bajo", e))?);
    }

    let mut daily_sales: Vec<DailySalesPoint> = Vec::new();
    let mut daily_stmt = conn
        .prepare(
            "
            SELECT substr(sold_at, 1, 10) AS sold_day, COALESCE(SUM(total), 0)
            FROM sales
            WHERE substr(sold_at, 1, 7) = ? AND COALESCE(sale_type, 'cash') <> 'internal'
            GROUP BY sold_day
            ORDER BY sold_day ASC
        ",
        )
        .map_err(|e| db_error("No se pudo preparar ventas diarias", e))?;
    let daily_rows = daily_stmt
        .query_map(params![&month_key], |row| {
            Ok(DailySalesPoint {
                sold_day: row.get(0)?,
                total: row.get(1)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar ventas diarias", e))?;
    for row in daily_rows {
        daily_sales.push(row.map_err(|e| db_error("No se pudo mapear ventas diarias", e))?);
    }

    Ok(DashboardSnapshotResponse {
        month: month_key,
        summary: DashboardSummary {
            sales_count,
            gross_total,
            paid_total,
            due_total,
            estimated_profit,
            internal_consumption_total,
            internal_operations_count,
            net_profit_after_internal,
        },
        payment_breakdown,
        top_products,
        low_products,
        low_stock_alerts,
        daily_sales,
    })
}

#[tauri::command]
fn dashboard_executive(
    app: AppHandle,
    month: Option<String>,
) -> Result<DashboardExecutiveResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let month_key = resolve_month_key(month)?;

    let month_start = NaiveDate::parse_from_str(&format!("{month_key}-01"), "%Y-%m-%d")
        .map_err(|_| "Mes invalido para dashboard ejecutivo".to_string())?;
    let previous_key = if month_start.month() == 1 {
        format!("{}-12", month_start.year() - 1)
    } else {
        format!("{}-{:02}", month_start.year(), month_start.month() - 1)
    };

    let current = summarize_month(&conn, &month_key)?;
    let previous = summarize_month(&conn, &previous_key)?;
    let (start_ts, end_ts) = month_bounds(&month_key)?;

    let mut peak_hours = Vec::new();
    let mut hour_stmt = conn
        .prepare(
            "
            SELECT
                CAST(substr(sold_at, 12, 2) AS INTEGER) AS hour,
                COALESCE(SUM(total), 0) AS total,
                COUNT(*) AS sales_count
            FROM sales
            WHERE sold_at >= ? AND sold_at < ? AND COALESCE(sale_type, 'cash') <> 'internal'
            GROUP BY hour
            ORDER BY total DESC, hour ASC
            LIMIT 8
        ",
        )
        .map_err(|e| db_error("No se pudo preparar horas pico", e))?;
    let hour_rows = hour_stmt
        .query_map(params![&start_ts, &end_ts], |row| {
            Ok(HourSalesPoint {
                hour: row.get(0)?,
                total: row.get(1)?,
                sales_count: row.get(2)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar horas pico", e))?;
    for row in hour_rows {
        peak_hours.push(row.map_err(|e| db_error("No se pudo mapear hora pico", e))?);
    }

    let mut category_profit = Vec::new();
    let mut cat_stmt = conn
        .prepare(
            "
            SELECT
                c.name,
                COALESCE(SUM(si.subtotal), 0) AS revenue,
                COALESCE(SUM((si.unit_price - si.cost_at_sale) * si.quantity), 0) AS profit
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id
            JOIN categories c ON c.id = p.category_id
            WHERE s.sold_at >= ? AND s.sold_at < ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
            GROUP BY c.name
            ORDER BY profit DESC, revenue DESC
            LIMIT 10
        ",
        )
        .map_err(|e| db_error("No se pudo preparar rentabilidad por categoria", e))?;
    let cat_rows = cat_stmt
        .query_map(params![&start_ts, &end_ts], |row| {
            Ok(CategoryProfitPoint {
                category_name: row.get(0)?,
                revenue: row.get(1)?,
                profit: row.get(2)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar rentabilidad por categoria", e))?;
    for row in cat_rows {
        category_profit.push(row.map_err(|e| db_error("No se pudo mapear categoria rentable", e))?);
    }

    Ok(DashboardExecutiveResponse {
        gross_delta_percent: compute_delta_percent(current.gross_total, previous.gross_total),
        profit_delta_percent: compute_delta_percent(
            current.estimated_profit,
            previous.estimated_profit,
        ),
        avg_ticket_delta_percent: compute_delta_percent(current.avg_ticket, previous.avg_ticket),
        current,
        previous,
        peak_hours,
        category_profit,
    })
}

#[tauri::command]
fn sales_report(
    app: AppHandle,
    from_date: String,
    to_date: String,
    payment_method: Option<String>,
    sales_limit: Option<i64>,
    products_limit: Option<i64>,
) -> Result<SalesReportResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let (start_ts, end_ts) = resolve_report_range(&from_date, &to_date)?;

    let filter_method = payment_method
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .filter(|value| !value.eq_ignore_ascii_case("todos"))
        .map(normalize_payment_method)
        .transpose()?;

    let safe_sales_limit = sales_limit.unwrap_or(200).clamp(1, 1200);
    let safe_products_limit = products_limit.unwrap_or(120).clamp(1, 600);
    let filter_internal_only = matches!(filter_method.as_deref(), Some("Consumo interno"));

    let (gross_total, paid_total, due_total, sales_count): (f64, f64, f64, i64) =
        if let Some(method) = &filter_method {
            if filter_internal_only {
                (0.0, 0.0, 0.0, 0)
            } else {
                conn.query_row(
                    "
                    SELECT
                        COALESCE(SUM(total), 0),
                        COALESCE(SUM(paid_amount), 0),
                        COALESCE(SUM(balance_due), 0),
                        COUNT(*)
                    FROM sales
                    WHERE sold_at >= ? AND sold_at < ? AND payment_method = ? AND COALESCE(sale_type, 'cash') <> 'internal'
                ",
                    params![&start_ts, &end_ts, method],
                    |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
                )
                .map_err(|e| db_error("No se pudo calcular resumen del reporte", e))?
            }
        } else {
            conn.query_row(
                "
                SELECT
                    COALESCE(SUM(total), 0),
                    COALESCE(SUM(paid_amount), 0),
                    COALESCE(SUM(balance_due), 0),
                    COUNT(*)
                FROM sales
                WHERE sold_at >= ? AND sold_at < ? AND COALESCE(sale_type, 'cash') <> 'internal'
            ",
                params![&start_ts, &end_ts],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
            )
            .map_err(|e| db_error("No se pudo calcular resumen del reporte", e))?
        };

    let estimated_profit: f64 = if let Some(method) = &filter_method {
        if filter_internal_only {
            0.0
        } else {
            conn.query_row(
                "
                SELECT COALESCE(SUM((si.unit_price - si.cost_at_sale) * si.quantity), 0)
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                WHERE s.sold_at >= ? AND s.sold_at < ? AND s.payment_method = ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
            ",
                params![&start_ts, &end_ts, method],
                |row| row.get(0),
            )
            .map_err(|e| db_error("No se pudo calcular ganancia del reporte", e))?
        }
    } else {
        conn.query_row(
            "
            SELECT COALESCE(SUM((si.unit_price - si.cost_at_sale) * si.quantity), 0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            WHERE s.sold_at >= ? AND s.sold_at < ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
        ",
            params![&start_ts, &end_ts],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo calcular ganancia del reporte", e))?
    };
    let (internal_consumption_total, internal_operations_count): (f64, i64) =
        if filter_internal_only {
            conn.query_row(
                "
                SELECT
                    COALESCE(SUM(total), 0),
                    COUNT(*)
                FROM sales
                WHERE sold_at >= ? AND sold_at < ? AND COALESCE(sale_type, 'cash') = 'internal'
            ",
                params![&start_ts, &end_ts],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .map_err(|e| db_error("No se pudo calcular consumo interno del reporte", e))?
        } else if filter_method.is_none() {
            conn.query_row(
                "
                SELECT
                    COALESCE(SUM(total), 0),
                    COUNT(*)
                FROM sales
                WHERE sold_at >= ? AND sold_at < ? AND COALESCE(sale_type, 'cash') = 'internal'
            ",
                params![&start_ts, &end_ts],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .map_err(|e| db_error("No se pudo calcular consumo interno del reporte", e))?
        } else {
            (0.0, 0)
        };
    let net_profit_after_internal = round_integer(estimated_profit - internal_consumption_total);

    let avg_ticket = if sales_count > 0 {
        gross_total / (sales_count as f64)
    } else {
        0.0
    };

    let mut payment_breakdown: Vec<PaymentBreakdownItem> = Vec::new();
    if let Some(method) = &filter_method {
        let total_for_method: f64 = conn
            .query_row(
                "
                SELECT COALESCE(SUM(paid_amount), 0)
                FROM sales
                WHERE sold_at >= ? AND sold_at < ? AND payment_method = ? AND COALESCE(sale_type, 'cash') <> 'internal'
            ",
                params![&start_ts, &end_ts, method],
                |row| row.get(0),
            )
            .map_err(|e| db_error("No se pudo calcular pagos por metodo en reporte", e))?;
        payment_breakdown.push(PaymentBreakdownItem {
            payment_method: method.clone(),
            total: total_for_method,
        });
    } else {
        let mut payment_stmt = conn
            .prepare(
                "
                SELECT payment_method, COALESCE(SUM(paid_amount), 0)
                FROM sales
                WHERE sold_at >= ? AND sold_at < ? AND paid_amount > 0 AND COALESCE(sale_type, 'cash') <> 'internal'
                GROUP BY payment_method
                ORDER BY COALESCE(SUM(paid_amount), 0) DESC, payment_method ASC
            ",
            )
            .map_err(|e| db_error("No se pudo preparar metodos de pago del reporte", e))?;
        let payment_rows = payment_stmt
            .query_map(params![&start_ts, &end_ts], |row| {
                Ok(PaymentBreakdownItem {
                    payment_method: row.get(0)?,
                    total: row.get(1)?,
                })
            })
            .map_err(|e| db_error("No se pudo listar metodos de pago del reporte", e))?;
        for row in payment_rows {
            payment_breakdown
                .push(row.map_err(|e| db_error("No se pudo mapear metodos del reporte", e))?);
        }
    }

    let mut sales: Vec<ReportSaleRow> = Vec::new();
    if let Some(method) = &filter_method {
        if filter_internal_only {
            let mut sales_stmt = conn
                .prepare(
                    "
                    SELECT
                        s.id, s.sold_at, c.name, s.payment_method,
                        s.total, s.paid_amount, s.balance_due, s.status
                    FROM sales s
                    LEFT JOIN customers c ON c.id = s.customer_id
                    WHERE s.sold_at >= ? AND s.sold_at < ? AND s.payment_method = ? AND COALESCE(s.sale_type, 'cash') = 'internal'
                    ORDER BY s.sold_at DESC, s.id DESC
                    LIMIT ?
                ",
                )
                .map_err(|e| db_error("No se pudo preparar ventas del reporte", e))?;
            let sale_rows = sales_stmt
                .query_map(
                    params![&start_ts, &end_ts, method, safe_sales_limit],
                    |row| {
                        Ok(ReportSaleRow {
                            sale_id: row.get(0)?,
                            sold_at: row.get(1)?,
                            customer_name: row.get(2)?,
                            payment_method: row.get(3)?,
                            total: row.get(4)?,
                            paid_amount: row.get(5)?,
                            balance_due: row.get(6)?,
                            status: row.get(7)?,
                        })
                    },
                )
                .map_err(|e| db_error("No se pudo listar ventas del reporte", e))?;
            for row in sale_rows {
                sales.push(row.map_err(|e| db_error("No se pudo mapear venta del reporte", e))?);
            }
        } else {
            let mut sales_stmt = conn
                .prepare(
                    "
                    SELECT
                        s.id, s.sold_at, c.name, s.payment_method,
                        s.total, s.paid_amount, s.balance_due, s.status
                    FROM sales s
                    LEFT JOIN customers c ON c.id = s.customer_id
                    WHERE s.sold_at >= ? AND s.sold_at < ? AND s.payment_method = ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
                    ORDER BY s.sold_at DESC, s.id DESC
                    LIMIT ?
                ",
                )
                .map_err(|e| db_error("No se pudo preparar ventas del reporte", e))?;
            let sale_rows = sales_stmt
                .query_map(
                    params![&start_ts, &end_ts, method, safe_sales_limit],
                    |row| {
                        Ok(ReportSaleRow {
                            sale_id: row.get(0)?,
                            sold_at: row.get(1)?,
                            customer_name: row.get(2)?,
                            payment_method: row.get(3)?,
                            total: row.get(4)?,
                            paid_amount: row.get(5)?,
                            balance_due: row.get(6)?,
                            status: row.get(7)?,
                        })
                    },
                )
                .map_err(|e| db_error("No se pudo listar ventas del reporte", e))?;
            for row in sale_rows {
                sales.push(row.map_err(|e| db_error("No se pudo mapear venta del reporte", e))?);
            }
        }
    } else {
        let mut sales_stmt = conn
            .prepare(
                "
                SELECT
                    s.id, s.sold_at, c.name, s.payment_method,
                    s.total, s.paid_amount, s.balance_due, s.status
                FROM sales s
                LEFT JOIN customers c ON c.id = s.customer_id
                WHERE s.sold_at >= ? AND s.sold_at < ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
                ORDER BY s.sold_at DESC, s.id DESC
                LIMIT ?
            ",
            )
            .map_err(|e| db_error("No se pudo preparar ventas del reporte", e))?;
        let sale_rows = sales_stmt
            .query_map(params![&start_ts, &end_ts, safe_sales_limit], |row| {
                Ok(ReportSaleRow {
                    sale_id: row.get(0)?,
                    sold_at: row.get(1)?,
                    customer_name: row.get(2)?,
                    payment_method: row.get(3)?,
                    total: row.get(4)?,
                    paid_amount: row.get(5)?,
                    balance_due: row.get(6)?,
                    status: row.get(7)?,
                })
            })
            .map_err(|e| db_error("No se pudo listar ventas del reporte", e))?;
        for row in sale_rows {
            sales.push(row.map_err(|e| db_error("No se pudo mapear venta del reporte", e))?);
        }
    }

    let mut products: Vec<ReportProductRow> = Vec::new();
    if let Some(method) = &filter_method {
        if filter_internal_only {
            let mut products_stmt = conn
                .prepare(
                    "
                    SELECT
                        si.product_name,
                        COALESCE(SUM(si.quantity), 0),
                        COALESCE(SUM(si.subtotal), 0),
                        COALESCE(SUM(si.cost_at_sale * si.quantity), 0),
                        COALESCE(SUM((si.unit_price - si.cost_at_sale) * si.quantity), 0)
                    FROM sale_items si
                    JOIN sales s ON s.id = si.sale_id
                    WHERE s.sold_at >= ? AND s.sold_at < ? AND s.payment_method = ? AND COALESCE(s.sale_type, 'cash') = 'internal'
                    GROUP BY si.product_name
                    HAVING COALESCE(SUM(si.quantity), 0) > 0
                    ORDER BY COALESCE(SUM(si.subtotal), 0) DESC, COALESCE(SUM(si.quantity), 0) DESC
                    LIMIT ?
                ",
                )
                .map_err(|e| db_error("No se pudo preparar productos del reporte", e))?;
            let product_rows = products_stmt
                .query_map(
                    params![&start_ts, &end_ts, method, safe_products_limit],
                    |row| {
                        Ok(ReportProductRow {
                            product_name: row.get(0)?,
                            quantity: row.get(1)?,
                            revenue: row.get(2)?,
                            cost_total: row.get(3)?,
                            profit: row.get(4)?,
                        })
                    },
                )
                .map_err(|e| db_error("No se pudo listar productos del reporte", e))?;
            for row in product_rows {
                products
                    .push(row.map_err(|e| db_error("No se pudo mapear productos del reporte", e))?);
            }
        } else {
            let mut products_stmt = conn
                .prepare(
                    "
                    SELECT
                        si.product_name,
                        COALESCE(SUM(si.quantity), 0),
                        COALESCE(SUM(si.subtotal), 0),
                        COALESCE(SUM(si.cost_at_sale * si.quantity), 0),
                        COALESCE(SUM((si.unit_price - si.cost_at_sale) * si.quantity), 0)
                    FROM sale_items si
                    JOIN sales s ON s.id = si.sale_id
                    WHERE s.sold_at >= ? AND s.sold_at < ? AND s.payment_method = ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
                    GROUP BY si.product_name
                    HAVING COALESCE(SUM(si.quantity), 0) > 0
                    ORDER BY COALESCE(SUM(si.subtotal), 0) DESC, COALESCE(SUM(si.quantity), 0) DESC
                    LIMIT ?
                ",
                )
                .map_err(|e| db_error("No se pudo preparar productos del reporte", e))?;
            let product_rows = products_stmt
                .query_map(
                    params![&start_ts, &end_ts, method, safe_products_limit],
                    |row| {
                        Ok(ReportProductRow {
                            product_name: row.get(0)?,
                            quantity: row.get(1)?,
                            revenue: row.get(2)?,
                            cost_total: row.get(3)?,
                            profit: row.get(4)?,
                        })
                    },
                )
                .map_err(|e| db_error("No se pudo listar productos del reporte", e))?;
            for row in product_rows {
                products
                    .push(row.map_err(|e| db_error("No se pudo mapear productos del reporte", e))?);
            }
        }
    } else {
        let mut products_stmt = conn
            .prepare(
                "
                SELECT
                    si.product_name,
                    COALESCE(SUM(si.quantity), 0),
                    COALESCE(SUM(si.subtotal), 0),
                    COALESCE(SUM(si.cost_at_sale * si.quantity), 0),
                    COALESCE(SUM((si.unit_price - si.cost_at_sale) * si.quantity), 0)
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                WHERE s.sold_at >= ? AND s.sold_at < ? AND COALESCE(s.sale_type, 'cash') <> 'internal'
                GROUP BY si.product_name
                HAVING COALESCE(SUM(si.quantity), 0) > 0
                ORDER BY COALESCE(SUM(si.subtotal), 0) DESC, COALESCE(SUM(si.quantity), 0) DESC
                LIMIT ?
            ",
            )
            .map_err(|e| db_error("No se pudo preparar productos del reporte", e))?;
        let product_rows = products_stmt
            .query_map(params![&start_ts, &end_ts, safe_products_limit], |row| {
                Ok(ReportProductRow {
                    product_name: row.get(0)?,
                    quantity: row.get(1)?,
                    revenue: row.get(2)?,
                    cost_total: row.get(3)?,
                    profit: row.get(4)?,
                })
            })
            .map_err(|e| db_error("No se pudo listar productos del reporte", e))?;
        for row in product_rows {
            products.push(row.map_err(|e| db_error("No se pudo mapear productos del reporte", e))?);
        }
    }

    Ok(SalesReportResponse {
        from_date: from_date.trim().to_string(),
        to_date: to_date.trim().to_string(),
        payment_method: filter_method,
        summary: ReportSummary {
            sales_count,
            gross_total,
            paid_total,
            due_total,
            estimated_profit,
            internal_consumption_total,
            internal_operations_count,
            net_profit_after_internal,
            avg_ticket,
        },
        payment_breakdown,
        sales,
        products,
    })
}

#[tauri::command]
fn create_sale(app: AppHandle, payload: CreateSaleRequest) -> Result<CreateSaleResponse, String> {
    if payload.items.is_empty() {
        return Err("No hay productos en el carrito".to_string());
    }

    let mut conn = open_db(&app)?;
    let _session = require_authenticated_user(&conn)?;
    let method = normalize_payment_method(&payload.payment_method)?;
    let is_internal_consumption = method == "Consumo interno";
    let customer_id = if is_internal_consumption {
        None
    } else {
        payload.customer_id
    };

    if let Some(customer_id) = customer_id {
        let active: Option<i64> = conn
            .query_row(
                "SELECT active FROM customers WHERE id = ?",
                params![customer_id],
                |row| row.get(0),
            )
            .optional()
            .map_err(|e| db_error("No se pudo validar cliente", e))?;

        match active {
            Some(1) => {}
            Some(_) => return Err("El cliente esta inactivo".to_string()),
            None => return Err("Cliente no encontrado".to_string()),
        }
    }

    let sold_at = Local::now().format("%Y-%m-%dT%H:%M:%S").to_string();
    let clean_notes = payload.notes.unwrap_or_default().trim().to_string();

    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de venta", e))?;
    tx.execute(
        "
        INSERT INTO sales(
            sold_at, payment_method, total, notes,
            customer_id, sale_type, paid_amount, balance_due, due_date, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ",
        params![
            sold_at,
            method,
            0.0f64,
            if clean_notes.is_empty() {
                None::<String>
            } else {
                Some(clean_notes)
            },
            customer_id,
            "cash",
            0.0f64,
            0.0f64,
            None::<String>,
            "paid"
        ],
    )
    .map_err(|e| db_error("No se pudo abrir venta", e))?;
    let sale_id = tx.last_insert_rowid();

    let mut total: f64 = 0.0;
    for item in &payload.items {
        let quantity = round_integer(item.quantity);
        if quantity <= 0.0 {
            return Err("Las cantidades deben ser mayores a cero".to_string());
        }

        let product = tx
            .query_row(
                "
                SELECT id, name, stock, cost, sale_price
                FROM products
                WHERE id = ? AND active = 1
            ",
                params![item.product_id],
                |row| {
                    Ok((
                        row.get::<_, i64>(0)?,
                        row.get::<_, String>(1)?,
                        round_integer(row.get::<_, f64>(2)?),
                        round_integer(row.get::<_, f64>(3)?),
                        round_integer(row.get::<_, f64>(4)?),
                    ))
                },
            )
            .optional()
            .map_err(|e| db_error("No se pudo leer producto para venta", e))?
            .ok_or_else(|| "Producto no encontrado o inactivo".to_string())?;

        let (product_id, product_name, stock_before, cost_at_sale, listed_unit_price) = product;
        let stock_after = round_integer(stock_before - quantity);
        if stock_after < 0.0 {
            return Err(format!("Stock insuficiente para {product_name}"));
        }

        let unit_price = if is_internal_consumption {
            cost_at_sale
        } else {
            listed_unit_price
        };
        let subtotal = round_integer(unit_price * quantity);
        total = round_integer(total + subtotal);

        tx.execute(
            "UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            params![stock_after, product_id],
        )
        .map_err(|e| db_error("No se pudo descontar stock por venta", e))?;

        tx.execute(
            "
            INSERT INTO sale_items(
                sale_id, product_id, product_name, quantity,
                unit_price, subtotal, cost_at_sale
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ",
            params![
                sale_id,
                product_id,
                product_name,
                quantity,
                unit_price,
                subtotal,
                cost_at_sale
            ],
        )
        .map_err(|e| db_error("No se pudo registrar item de venta", e))?;

        tx.execute(
            "
            INSERT INTO stock_movements(
                product_id, movement_type, quantity, stock_before,
                stock_after, unit_cost, reference_type, reference_id, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ",
            params![
                product_id,
                if is_internal_consumption {
                    "manual_out"
                } else {
                    "sale"
                },
                -quantity,
                stock_before,
                stock_after,
                cost_at_sale,
                if is_internal_consumption {
                    "internal_consumption"
                } else {
                    "sale"
                },
                sale_id,
                if is_internal_consumption {
                    "Consumo interno"
                } else {
                    "Venta POS"
                }
            ],
        )
        .map_err(|e| db_error("No se pudo registrar movimiento de venta", e))?;
    }

    let raw_paid = if is_internal_consumption {
        if round_non_negative_integer(payload.paid_amount.unwrap_or(0.0)) > 0.0 {
            return Err("Consumo interno no admite monto pagado".to_string());
        }
        0.0
    } else {
        round_integer(
            payload
                .paid_amount
                .unwrap_or_else(|| if method == "Deuda" { 0.0 } else { total }),
        )
    };
    if raw_paid < 0.0 {
        return Err("El pago no puede ser negativo".to_string());
    }
    if raw_paid - total > 1e-9 {
        return Err("El pago no puede superar el total".to_string());
    }

    let balance_due = if is_internal_consumption {
        0.0
    } else {
        round_integer((total - raw_paid).max(0.0))
    };
    if balance_due > 1e-9 && customer_id.is_none() {
        return Err("Para pago parcial o deuda debes seleccionar un cliente".to_string());
    }
    let due_date = if is_internal_consumption {
        None
    } else if balance_due > 1e-9 {
        Some(parse_due_date_or_default(payload.due_date.clone())?)
    } else {
        None
    };

    let sale_type = if is_internal_consumption {
        "internal".to_string()
    } else if balance_due > 1e-9 {
        "credit".to_string()
    } else {
        "cash".to_string()
    };
    let status = if is_internal_consumption {
        "internal".to_string()
    } else if balance_due <= 1e-9 {
        "paid".to_string()
    } else if raw_paid > 0.0 {
        "partial".to_string()
    } else {
        "credit".to_string()
    };
    let sale_method = if is_internal_consumption {
        "Consumo interno".to_string()
    } else if method == "Deuda" && raw_paid > 1e-9 {
        "Efectivo".to_string()
    } else {
        method.clone()
    };

    tx.execute(
        "UPDATE sales SET payment_method = ?, sale_type = ?, total = ?, paid_amount = ?, balance_due = ?, due_date = ?, status = ? WHERE id = ?",
        params![sale_method, sale_type, total, raw_paid, balance_due, due_date.clone(), status, sale_id],
    )
    .map_err(|e| db_error("No se pudo cerrar venta", e))?;

    let mut initial_payment_method: Option<String> = None;
    if let Some(customer_id) = customer_id {
        if raw_paid > 0.0 {
            let selected = payload
                .initial_payment_method
                .as_deref()
                .unwrap_or(payload.payment_method.as_str());
            let mut applied = normalize_payment_method(selected)?;
            if applied == "Deuda" || applied == "Consumo interno" {
                applied = "Efectivo".to_string();
            }
            tx.execute(
                "
                INSERT INTO payments(
                    sale_id, customer_id, amount, payment_method,
                    note, reference_type, reference_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ",
                params![
                    sale_id,
                    customer_id,
                    raw_paid,
                    applied,
                    "Pago inicial de venta",
                    "sale_payment",
                    sale_id
                ],
            )
            .map_err(|e| db_error("No se pudo registrar pago inicial", e))?;
            initial_payment_method = Some(applied);
        }
    }

    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar venta", e))?;

    Ok(CreateSaleResponse {
        sale_id,
        sold_at,
        total,
        payment_method: sale_method,
        sale_type,
        customer_id,
        paid_amount: raw_paid,
        balance_due,
        due_date,
        status,
        initial_payment_method,
    })
}

#[tauri::command]
fn reverse_sale(app: AppHandle, payload: ReverseSaleRequest) -> Result<ReverseSaleResponse, String> {
    if payload.sale_id <= 0 {
        return Err("Venta invalida".to_string());
    }

    let mut conn = open_db(&app)?;
    let admin = require_admin_user(&conn)?;
    let reason_text = payload.reason.unwrap_or_default().trim().to_string();
    let tx = conn
        .transaction()
        .map_err(|e| db_error("No se pudo iniciar transaccion de reversion de venta", e))?;

    let already_reversed: Option<i64> = tx
        .query_row(
            "SELECT id FROM sale_reversals WHERE sale_id = ? LIMIT 1",
            params![payload.sale_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| db_error("No se pudo validar estado de reversion de venta", e))?;
    if already_reversed.is_some() {
        return Err("Esa venta ya fue revertida".to_string());
    }

    let (
        sold_at,
        payment_method,
        sale_type,
        status,
        customer_id,
        total,
        paid_amount,
        balance_due,
    ): (String, String, String, String, Option<i64>, f64, f64, f64) = tx
        .query_row(
            "
            SELECT
                sold_at, payment_method, COALESCE(sale_type, 'cash'), COALESCE(status, 'paid'),
                customer_id, total, paid_amount, balance_due
            FROM sales
            WHERE id = ?
            LIMIT 1
        ",
            params![payload.sale_id],
            |row| {
                Ok((
                    row.get(0)?,
                    row.get(1)?,
                    row.get(2)?,
                    row.get(3)?,
                    row.get(4)?,
                    round_integer(row.get::<_, f64>(5)?),
                    round_integer(row.get::<_, f64>(6)?),
                    round_integer(row.get::<_, f64>(7)?),
                ))
            },
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar venta para revertir", e))?
        .ok_or_else(|| "Venta no encontrada".to_string())?;

    let mut item_stmt = tx
        .prepare(
            "
            SELECT product_id, product_name, quantity, cost_at_sale
            FROM sale_items
            WHERE sale_id = ?
            ORDER BY id ASC
        ",
        )
        .map_err(|e| db_error("No se pudo preparar items de venta para revertir", e))?;
    let item_rows = item_stmt
        .query_map(params![payload.sale_id], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, String>(1)?,
                round_integer(row.get::<_, f64>(2)?),
                round_integer(row.get::<_, f64>(3)?),
            ))
        })
        .map_err(|e| db_error("No se pudieron listar items de venta para revertir", e))?;

    let mut items: Vec<(i64, String, f64, f64)> = Vec::new();
    for row in item_rows {
        items.push(row.map_err(|e| db_error("No se pudo mapear item de venta para revertir", e))?);
    }
    drop(item_stmt);
    if items.is_empty() {
        return Err("La venta no tiene items para revertir".to_string());
    }

    let mut restored_units = 0.0;
    for (product_id, product_name, quantity, cost_at_sale) in &items {
        let current_stock: f64 = tx
            .query_row(
                "SELECT stock FROM products WHERE id = ? LIMIT 1",
                params![product_id],
                |row| Ok(round_integer(row.get::<_, f64>(0)?)),
            )
            .optional()
            .map_err(|e| db_error("No se pudo consultar producto al revertir venta", e))?
            .ok_or_else(|| format!("Producto no encontrado para revertir: {product_name}"))?;

        let stock_after = round_integer(current_stock + quantity);
        tx.execute(
            "
            UPDATE products
            SET stock = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ",
            params![stock_after, product_id],
        )
        .map_err(|e| db_error("No se pudo restaurar stock al revertir venta", e))?;

        let movement_note = if reason_text.is_empty() {
            format!("Reversion venta #{}", payload.sale_id)
        } else {
            format!("Reversion venta #{}: {reason_text}", payload.sale_id)
        };
        tx.execute(
            "
            INSERT INTO stock_movements(
                product_id, movement_type, quantity, stock_before,
                stock_after, unit_cost, reference_type, reference_id, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ",
            params![
                product_id,
                "manual_in",
                quantity,
                current_stock,
                stock_after,
                cost_at_sale,
                "sale_reversal",
                payload.sale_id,
                movement_note
            ],
        )
        .map_err(|e| db_error("No se pudo registrar movimiento de reversion de venta", e))?;

        restored_units = round_integer(restored_units + quantity);
    }

    tx.execute(
        "
        INSERT INTO sale_reversals(
            sale_id, sold_at, payment_method, sale_type, status,
            customer_id, total, paid_amount, balance_due,
            items_count, reversed_by_user_id, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ",
        params![
            payload.sale_id,
            sold_at,
            payment_method,
            sale_type,
            status,
            customer_id,
            total,
            paid_amount,
            balance_due,
            items.len() as i64,
            admin.id,
            if reason_text.is_empty() {
                None::<String>
            } else {
                Some(reason_text.clone())
            }
        ],
    )
    .map_err(|e| db_error("No se pudo guardar auditoria de reversion de venta", e))?;

    let removed_payments = tx
        .execute("DELETE FROM payments WHERE sale_id = ?", params![payload.sale_id])
        .map_err(|e| db_error("No se pudieron limpiar pagos de la venta revertida", e))?
        as i64;

    tx.execute(
        "
        DELETE FROM stock_movements
        WHERE reference_id = ?
          AND reference_type IN ('sale', 'internal_consumption')
    ",
        params![payload.sale_id],
    )
    .map_err(|e| db_error("No se pudieron limpiar movimientos originales de la venta", e))?;

    let deleted_sales = tx
        .execute("DELETE FROM sales WHERE id = ?", params![payload.sale_id])
        .map_err(|e| db_error("No se pudo eliminar venta revertida", e))?;
    if deleted_sales == 0 {
        return Err("Venta no encontrada para eliminar".to_string());
    }

    let reversed_at: String = tx
        .query_row(
            "SELECT reversed_at FROM sale_reversals WHERE sale_id = ?",
            params![payload.sale_id],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo leer fecha de reversion de venta", e))?;

    tx.commit()
        .map_err(|e| db_error("No se pudo confirmar reversion de venta", e))?;

    Ok(ReverseSaleResponse {
        sale_id: payload.sale_id,
        reversed_at,
        restored_items: items.len() as i64,
        restored_units,
        removed_payments,
    })
}

#[tauri::command]
fn ticket_settings(app: AppHandle) -> Result<TicketSettingsResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    Ok(read_ticket_settings(&conn))
}

#[tauri::command]
fn update_ticket_settings(
    app: AppHandle,
    payload: UpdateTicketSettingsRequest,
) -> Result<TicketSettingsResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;

    if let Some(width) = payload.paper_width_mm {
        if width != 58 && width != 80 {
            return Err("Ancho invalido. Usa 58 o 80 mm".to_string());
        }
        upsert_setting(&conn, TICKET_PAPER_WIDTH_KEY, &width.to_string())?;
    }
    if let Some(value) = payload.store_name {
        upsert_setting(&conn, TICKET_STORE_NAME_KEY, value.trim())?;
    }
    if let Some(value) = payload.tax_id {
        upsert_setting(&conn, TICKET_TAX_ID_KEY, value.trim())?;
    }
    if let Some(value) = payload.address {
        upsert_setting(&conn, TICKET_ADDRESS_KEY, value.trim())?;
    }
    if let Some(value) = payload.phone {
        upsert_setting(&conn, TICKET_PHONE_KEY, value.trim())?;
    }
    if let Some(value) = payload.header_text {
        upsert_setting(&conn, TICKET_HEADER_KEY, value.trim())?;
    }
    if let Some(value) = payload.footer_text {
        upsert_setting(&conn, TICKET_FOOTER_KEY, value.trim())?;
    }
    if let Some(value) = payload.logo_path {
        upsert_setting(&conn, TICKET_LOGO_PATH_KEY, value.trim())?;
    }
    if let Some(show_logo) = payload.show_logo {
        upsert_setting(
            &conn,
            TICKET_SHOW_LOGO_KEY,
            if show_logo { "1" } else { "0" },
        )?;
    }

    Ok(read_ticket_settings(&conn))
}

#[tauri::command]
fn generate_sale_ticket(
    app: AppHandle,
    sale_id: i64,
    copy_type: Option<String>,
) -> Result<SaleTicketResponse, String> {
    if sale_id <= 0 {
        return Err("Venta invalida para ticket".to_string());
    }
    let conn = open_db(&app)?;
    let session = require_authenticated_user(&conn)?;

    let (sold_at, payment_method, total, paid_amount, balance_due, customer_name) = conn
        .query_row(
            "
            SELECT s.sold_at, s.payment_method, s.total, s.paid_amount, s.balance_due, c.name
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            WHERE s.id = ?
            LIMIT 1
        ",
            params![sale_id],
            |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, f64>(2)?,
                    row.get::<_, f64>(3)?,
                    row.get::<_, f64>(4)?,
                    row.get::<_, Option<String>>(5)?,
                ))
            },
        )
        .optional()
        .map_err(|e| db_error("No se pudo consultar venta para ticket", e))?
        .ok_or_else(|| "Venta no encontrada".to_string())?;

    let mut items = Vec::new();
    let mut item_stmt = conn
        .prepare(
            "
            SELECT product_name, quantity, unit_price, subtotal
            FROM sale_items
            WHERE sale_id = ?
            ORDER BY id ASC
        ",
        )
        .map_err(|e| db_error("No se pudo preparar items para ticket", e))?;
    let item_rows = item_stmt
        .query_map(params![sale_id], |row| {
            Ok(SaleTicketItem {
                product_name: row.get(0)?,
                quantity: row.get(1)?,
                unit_price: row.get(2)?,
                subtotal: row.get(3)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar items para ticket", e))?;
    for row in item_rows {
        items.push(row.map_err(|e| db_error("No se pudo mapear item de ticket", e))?);
    }

    let settings = read_ticket_settings(&conn);
    let clean_copy_type = copy_type
        .unwrap_or_else(|| "original".to_string())
        .trim()
        .to_lowercase();
    let copy = if clean_copy_type.is_empty() {
        "original".to_string()
    } else {
        clean_copy_type
    };
    let printed_at = Local::now().format("%Y-%m-%dT%H:%M:%S").to_string();
    conn.execute(
        "
        INSERT INTO ticket_prints(sale_id, printed_at, printed_by_user_id, copy_type)
        VALUES (?, ?, ?, ?)
    ",
        params![sale_id, &printed_at, session.id, &copy],
    )
    .map_err(|e| db_error("No se pudo registrar impresion de ticket", e))?;

    let body_text = build_sale_ticket_body(
        &settings,
        sale_id,
        &sold_at,
        customer_name.as_deref(),
        &payment_method,
        total,
        paid_amount,
        balance_due,
        &items,
        &copy,
    );

    Ok(SaleTicketResponse {
        sale_id,
        printed_at,
        paper_width_mm: settings.paper_width_mm,
        title: format!("Ticket venta #{sale_id}"),
        body_text,
        total,
        paid_amount,
        balance_due,
        payment_method,
        customer_name,
        copy_type: copy,
        items,
    })
}

#[tauri::command]
fn list_ticket_prints(app: AppHandle, limit: Option<i64>) -> Result<Vec<TicketPrintRow>, String> {
    let conn = open_db(&app)?;
    let _session = require_authenticated_user(&conn)?;
    let safe_limit = limit.unwrap_or(80).clamp(1, 500);

    let mut stmt = conn
        .prepare(
            "
            SELECT
                tp.id, tp.sale_id, tp.printed_at, tp.copy_type,
                s.total, s.paid_amount, s.balance_due, s.payment_method, c.name
            FROM ticket_prints tp
            JOIN sales s ON s.id = tp.sale_id
            LEFT JOIN customers c ON c.id = s.customer_id
            ORDER BY tp.printed_at DESC, tp.id DESC
            LIMIT ?
        ",
        )
        .map_err(|e| db_error("No se pudo preparar historial de tickets", e))?;
    let rows = stmt
        .query_map(params![safe_limit], |row| {
            Ok(TicketPrintRow {
                id: row.get(0)?,
                sale_id: row.get(1)?,
                printed_at: row.get(2)?,
                copy_type: row.get(3)?,
                total: row.get(4)?,
                paid_amount: row.get(5)?,
                balance_due: row.get(6)?,
                payment_method: row.get(7)?,
                customer_name: row.get(8)?,
            })
        })
        .map_err(|e| db_error("No se pudo listar historial de tickets", e))?;

    let mut result = Vec::new();
    for row in rows {
        result.push(row.map_err(|e| db_error("No se pudo mapear ticket impreso", e))?);
    }
    Ok(result)
}

#[tauri::command]
fn quality_audit(app: AppHandle) -> Result<QualityAuditResponse, String> {
    let conn = open_db(&app)?;
    let _admin = require_admin_user(&conn)?;
    let checked_at = Local::now().format("%Y-%m-%dT%H:%M:%S").to_string();
    let mut issues: Vec<QualityIssue> = Vec::new();

    let products_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM products", [], |row| row.get(0))
        .map_err(|e| db_error("No se pudo contar productos", e))?;
    let sales_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM sales", [], |row| row.get(0))
        .map_err(|e| db_error("No se pudo contar ventas", e))?;
    let customers_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM customers", [], |row| row.get(0))
        .map_err(|e| db_error("No se pudo contar clientes", e))?;

    let negative_stock_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM products WHERE stock < 0", [], |row| {
            row.get(0)
        })
        .map_err(|e| db_error("No se pudo auditar stock negativo", e))?;
    if negative_stock_count > 0 {
        issues.push(QualityIssue {
            code: "NEGATIVE_STOCK".to_string(),
            severity: "critical".to_string(),
            detail: format!("Hay {negative_stock_count} productos con stock negativo."),
        });
    }

    let mismatched_sales: i64 = conn
        .query_row(
            "
            SELECT COUNT(*)
            FROM sales s
            LEFT JOIN (
                SELECT sale_id, COALESCE(SUM(subtotal), 0) AS items_total
                FROM sale_items
                GROUP BY sale_id
            ) si ON si.sale_id = s.id
            WHERE ABS(COALESCE(si.items_total, 0) - s.total) > 0.01
        ",
            [],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo auditar totales de venta", e))?;
    if mismatched_sales > 0 {
        issues.push(QualityIssue {
            code: "SALES_TOTAL_MISMATCH".to_string(),
            severity: "critical".to_string(),
            detail: format!("Hay {mismatched_sales} ventas con total inconsistente vs items."),
        });
    }

    let missing_due_date: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM sales WHERE balance_due > 0 AND (due_date IS NULL OR trim(due_date) = '')",
            [],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo auditar vencimientos de deuda", e))?;
    if missing_due_date > 0 {
        issues.push(QualityIssue {
            code: "MISSING_DUE_DATE".to_string(),
            severity: "warning".to_string(),
            detail: format!("Hay {missing_due_date} ventas con deuda sin fecha de vencimiento."),
        });
    }

    let stale_debt_over_limit: i64 = conn
        .query_row(
            "
            SELECT COUNT(*)
            FROM customers c
            JOIN (
                SELECT customer_id, COALESCE(SUM(CASE WHEN balance_due > 0 THEN balance_due ELSE 0 END), 0) AS debt_total
                FROM sales
                GROUP BY customer_id
            ) d ON d.customer_id = c.id
            WHERE d.debt_total > c.alert_limit
        ",
            [],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo auditar clientes sobre limite", e))?;
    if stale_debt_over_limit > 0 {
        issues.push(QualityIssue {
            code: "CUSTOMER_OVER_LIMIT".to_string(),
            severity: "warning".to_string(),
            detail: format!("Hay {stale_debt_over_limit} clientes por encima del limite de deuda."),
        });
    }

    let orphan_sale_items: i64 = conn
        .query_row(
            "
            SELECT COUNT(*)
            FROM sale_items si
            LEFT JOIN sales s ON s.id = si.sale_id
            WHERE s.id IS NULL
        ",
            [],
            |row| row.get(0),
        )
        .map_err(|e| db_error("No se pudo auditar items huerfanos", e))?;
    if orphan_sale_items > 0 {
        issues.push(QualityIssue {
            code: "ORPHAN_SALE_ITEMS".to_string(),
            severity: "critical".to_string(),
            detail: format!("Hay {orphan_sale_items} items de venta sin cabecera asociada."),
        });
    }

    Ok(QualityAuditResponse {
        checked_at,
        issues,
        products_count,
        sales_count,
        customers_count,
    })
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            health_check,
            payment_methods,
            auth_bootstrap_status,
            auth_bootstrap_create_admin,
            auth_session,
            auth_login,
            auth_logout,
            list_users,
            create_user,
            update_user,
            delete_user,
            backup_status,
            backup_config,
            update_backup_config,
            list_backup_files,
            create_backup,
            restore_backup,
            run_backup_maintenance,
            verify_backup_file,
            search_products,
            get_product_by_barcode,
            list_favorite_products,
            set_product_favorite,
            list_customers,
            create_customer,
            update_customer,
            customer_account_snapshot,
            register_customer_payment,
            list_categories,
            list_categories_admin,
            create_category,
            update_category,
            delete_category,
            list_deleted_categories,
            restore_deleted_category,
            list_products_admin,
            create_product,
            update_product,
            inventory_list_movements,
            register_inventory_movement,
            reverse_stock_movement,
            list_recent_stock_movements,
            quick_stock_lookup_by_barcode,
            quick_stock_add_by_barcode,
            dashboard_snapshot,
            dashboard_executive,
            sales_report,
            create_sale,
            reverse_sale,
            ticket_settings,
            update_ticket_settings,
            generate_sale_ticket,
            list_ticket_prints,
            quality_audit,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
