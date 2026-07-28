import type { AuthorityClass } from "../lib/spatial-runtime";

const label: Record<AuthorityClass, string> = {
  authoritative: "Source evidence",
  verified: "Independently verified",
  measured: "Measured, not verified",
  observed: "Observed",
  inferred: "Inferred",
  generated: "Generated",
  derived_non_authoritative: "Derived, non-authoritative"
};

export function AuthorityBadge({ authority, confidence }: { authority: AuthorityClass; confidence?: number }): React.ReactNode {
  const confidenceText = confidence === undefined ? "" : ` · confidence ${(confidence * 100).toFixed(0)}%`;
  return <span className={`authority authority-${authority}`} aria-label={`${label[authority]}${confidenceText}`}>{label[authority]}{confidenceText}</span>;
}
