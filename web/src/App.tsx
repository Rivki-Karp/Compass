import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { EmployeePage } from "./routes/EmployeePage";
import { NotFound } from "./routes/NotFound";
import { RepPage } from "./routes/RepPage";

// The style guide is a dev-only route: it is not part of the production bundle.
const Styleguide = import.meta.env.DEV
  ? lazy(() => import("./routes/Styleguide").then((m) => ({ default: m.Styleguide })))
  : null;

/** The UI's routes (the page tests render them in a MemoryRouter). */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<EmployeePage />} />
      <Route path="/rep" element={<RepPage />} />
      {Styleguide ? (
        <Route
          path="/__styleguide"
          element={
            <Suspense fallback={null}>
              <Styleguide />
            </Suspense>
          }
        />
      ) : null}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
