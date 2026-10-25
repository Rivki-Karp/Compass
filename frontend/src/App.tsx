import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { AdminPage } from "./admin/AdminPage";
import { AuthProvider } from "./auth/AuthContext";
import { useAuth } from "./auth/context";
import { DemoBanner } from "./home/DemoBanner";
import { HomeEntry } from "./home/HomeEntry";
import { Landing } from "./landing/Landing";
import { EmployeePage } from "./routes/EmployeePage";
import { NotFound } from "./routes/NotFound";
import { RegisterPage } from "./routes/RegisterPage";
import { RepPage } from "./routes/RepPage";

// The style guide is a dev-only route: it is not part of the production bundle.
const Styleguide = import.meta.env.DEV
  ? lazy(() => import("./routes/Styleguide").then((m) => ({ default: m.Styleguide })))
  : null;

/** One conversation, by its address: remounted for each, so nothing carries over. */
function Conversation() {
  const { conversationId } = useParams();
  return <EmployeePage key={conversationId} conversationId={conversationId} />;
}

/** Accounts on (COMPASS_AUTH=1): a visitor sees the landing page; a login opens the app. */
function AccountRoutes() {
  const { status, user } = useAuth();
  const loggedIn = status === "in";
  return (
    <>
      <DemoBanner />
      <Routes>
      <Route path="/" element={loggedIn ? <HomeEntry /> : <Landing />} />
      <Route path="/new" element={loggedIn ? <HomeEntry /> : <Navigate to="/" replace />} />
      <Route path="/c/:conversationId" element={loggedIn ? <Conversation /> : <Navigate to="/" replace />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/admin"
        element={
          !loggedIn ? <Navigate to="/" replace /> : user?.role === "admin" ? <AdminPage /> : <NotFound />
        }
      />
      <Route
        path="/rep"
        element={
          !loggedIn ? <Navigate to="/" replace /> : user?.role === "rep" ? <RepPage /> : <NotFound />
        }
      />
      <Route path="*" element={<NotFound />} />
      </Routes>
    </>
  );
}

/** The UI's routes (the page tests render them in a MemoryRouter). With accounts off, as ever. */
export function AppRoutes() {
  const { status } = useAuth();
  if (status === "loading") {
    return <div role="status" aria-label="טוען" className="min-h-screen bg-ground" />;
  }
  if (status !== "off") return <AccountRoutes />;
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
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
