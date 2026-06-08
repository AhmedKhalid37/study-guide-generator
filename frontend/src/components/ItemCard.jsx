import React from "react";

// Inner item card (.item-card). Anatomy:
//   .item-top : date (left) + `trailing` slot (right — a StatusPill /
//               ProviderPill, or a top-right icon)
//   .item-title / .item-desc (description is line-clamped by the CSS)
//   .item-meta : `meta` slot (compose .mtoken spans here)
// Stays a div so it can host pills/buttons without nesting interactive
// elements; pass `onClick` to make the whole card clickable.
export default function ItemCard({ date, title, description, trailing, meta, className = "", children, ...rest }) {
  return (
    <div className={`item-card ${className}`.trim()} {...rest}>
      {(date != null || trailing != null) && (
        <div className="item-top">
          {date != null ? <span className="item-date">{date}</span> : <span />}
          {trailing}
        </div>
      )}
      {title != null && <div className="item-title">{title}</div>}
      {description != null && <div className="item-desc">{description}</div>}
      {meta != null && <div className="item-meta">{meta}</div>}
      {children}
    </div>
  );
}
