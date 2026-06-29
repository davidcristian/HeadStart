/** Product logo + wordmark used in the app shell and public pages. */

import { Link } from "react-router-dom";

export function Brand({ className, to = "/" }: { className?: string; to?: string }) {
  return (
    <Link to={to} className={className ? `brand ${className}` : "brand"}>
      <span className="brand-mark" aria-hidden="true">
        HS
      </span>
      <span className="brand-name">HeadStart</span>
    </Link>
  );
}
