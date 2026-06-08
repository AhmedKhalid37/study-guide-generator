import React from "react";

// Labelled form-field wrapper: a `.field-label`, the control (children — e.g. an
// <input>/<textarea> with the `.field` class), and an optional hint or error
// line. `error` takes precedence over `hint` when both are provided.
export default function Field({ label, htmlFor, hint, error, className = "", children, ...rest }) {
  return (
    <div className={`field-group ${className}`.trim()} {...rest}>
      {label != null && (
        <label className="field-label" htmlFor={htmlFor}>
          {label}
        </label>
      )}
      {children}
      {error != null ? (
        <div className="field-error">{error}</div>
      ) : hint != null ? (
        <div className="field-hint">{hint}</div>
      ) : null}
    </div>
  );
}
