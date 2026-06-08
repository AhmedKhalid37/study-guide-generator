import React from "react";

// Dark section panel (.panel). Optional header row (.panel-head) with a serif
// `title` on the left and an `action` node on the right (e.g. a "View all"
// .panel-link or a Button). Body is the children.
export default function Panel({ title, action, className = "", children, ...rest }) {
  const hasHeader = title != null || action != null;
  return (
    <section className={`panel ${className}`.trim()} {...rest}>
      {hasHeader && (
        <div className="panel-head">
          {title != null && <div className="section-title">{title}</div>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
