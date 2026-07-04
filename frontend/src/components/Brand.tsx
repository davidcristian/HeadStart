/** Product logo + wordmark used in the app shell and public pages. */

import { Link } from "react-router-dom";

export function Brand({ className, to = "/" }: { className?: string; to?: string }) {
  return (
    <Link to={to} className={className ? `brand ${className}` : "brand"}>
      <img className="brand-mark" src="/icon.svg" alt="" aria-hidden="true" />
      <span className="brand-name">HeadStart</span>
    </Link>
  );
}
