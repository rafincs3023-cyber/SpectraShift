import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="page">
      <div className="page-header">
        <h1>Page not found</h1>
        <p className="page-subtitle">
          The page you're looking for doesn't exist.
        </p>
      </div>
      <Link to="/" className="btn btn-primary">
        Back to home
      </Link>
    </div>
  );
}
