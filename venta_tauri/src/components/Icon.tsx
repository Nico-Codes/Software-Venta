import React from "react";

export type IconName =
  | "sale"
  | "stock"
  | "utilities"
  | "dashboard"
  | "products"
  | "categories"
  | "inventory"
  | "reports"
  | "customers"
  | "users"
  | "backup"
  | "tickets"
  | "quality"
  | "chevron-right"
  | "chevron-down"
  | "spark"
  | "scan"
  | "wallet"
  | "print"
  | "star";

type IconProps = {
  name: IconName;
  size?: number;
  strokeWidth?: number;
  className?: string;
};

const strokeCommon = {
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function Icon({ name, size = 18, strokeWidth = 1.9, className }: IconProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      {name === "sale" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M4 6h16v12H4z" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M8 10h8M8 14h5" />
        </>
      )}
      {name === "stock" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M4 10l8-6 8 6v10H4z" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M9 14h6" />
        </>
      )}
      {name === "utilities" && (
        <>
          <circle {...strokeCommon} strokeWidth={strokeWidth} cx="12" cy="12" r="7" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M12 8v8M8 12h8" />
        </>
      )}
      {name === "dashboard" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M4 12a8 8 0 1 1 16 0" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M12 12l4-4" />
        </>
      )}
      {name === "products" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M4 7h16v10H4z" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M8 11h8" />
        </>
      )}
      {name === "categories" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M6 4h12l2 4-8 12L4 8z" />
          <circle {...strokeCommon} strokeWidth={strokeWidth} cx="10" cy="8" r="1" />
        </>
      )}
      {name === "inventory" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M4 6h16v14H4z" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M8 10h8M8 14h8" />
        </>
      )}
      {name === "reports" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M5 18V9M11 18V6M17 18v-4" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M3 20h18" />
        </>
      )}
      {name === "customers" && (
        <>
          <circle {...strokeCommon} strokeWidth={strokeWidth} cx="9" cy="9" r="3" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M4 18c0-2.5 2-4 5-4s5 1.5 5 4" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M16 8h4M18 6v4" />
        </>
      )}
      {name === "users" && (
        <>
          <circle {...strokeCommon} strokeWidth={strokeWidth} cx="8" cy="9" r="3" />
          <circle {...strokeCommon} strokeWidth={strokeWidth} cx="16" cy="10" r="2" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M3 19c0-2.7 2.2-4.2 5-4.2s5 1.5 5 4.2" />
        </>
      )}
      {name === "backup" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M12 4v8" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M8 8l4-4 4 4" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M5 14h14v6H5z" />
        </>
      )}
      {name === "tickets" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M6 5h12v14H6z" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M9 9h6M9 13h6" />
        </>
      )}
      {name === "quality" && (
        <>
          <circle {...strokeCommon} strokeWidth={strokeWidth} cx="12" cy="12" r="8" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M8.5 12.5l2.2 2.2L15.7 9.7" />
        </>
      )}
      {name === "chevron-right" && (
        <polyline {...strokeCommon} strokeWidth={strokeWidth} points="9 6 15 12 9 18" />
      )}
      {name === "chevron-down" && (
        <polyline {...strokeCommon} strokeWidth={strokeWidth} points="6 9 12 15 18 9" />
      )}
      {name === "spark" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" />
        </>
      )}
      {name === "scan" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M4 7V5h4M20 7V5h-4M4 17v2h4M20 17v2h-4" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M7 12h10" />
        </>
      )}
      {name === "wallet" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M4 7h16v10H4z" />
          <circle {...strokeCommon} strokeWidth={strokeWidth} cx="16" cy="12" r="1" />
        </>
      )}
      {name === "print" && (
        <>
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M7 8V4h10v4" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M6 10h12a2 2 0 0 1 2 2v4H4v-4a2 2 0 0 1 2-2z" />
          <path {...strokeCommon} strokeWidth={strokeWidth} d="M7 14h10v6H7z" />
        </>
      )}
      {name === "star" && (
        <path
          {...strokeCommon}
          strokeWidth={strokeWidth}
          d="M12 4l2.4 4.8 5.2.7-3.8 3.7.9 5.2L12 16l-4.7 2.4.9-5.2L4.4 9.5l5.2-.7z"
        />
      )}
    </svg>
  );
}
