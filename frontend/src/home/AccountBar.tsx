import { Link } from "react-router-dom";
import type { AuthUser } from "../auth/authStore";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";

/** The user in the header (the name with its initial) and "יציאה"; for the roles that have a
 * screen of their own, a link to it. `onMenu`: on a phone, the button that opens the drawer of
 * conversations. */
export function AccountBar({
  user,
  onLogout,
  onMenu,
}: {
  user: AuthUser;
  onLogout: () => void;
  onMenu?: () => void;
}) {
  return (
    <>
      {onMenu ? (
        <Button variant="secondary" onClick={onMenu} className="border-white/30 bg-transparent text-white hover:bg-white/10">
          <Icon name="book" size={16} />
          השיחות שלי
        </Button>
      ) : null}
      {user.role === "admin" ? (
        <Link
          to="/admin"
          className="inline-flex min-h-11 items-center rounded-control px-3 text-[14px] text-white underline"
        >
          ניהול משתמשים
        </Link>
      ) : null}
      {user.role === "rep" ? (
        <Link
          to="/rep"
          className="inline-flex min-h-11 items-center rounded-control px-3 text-[14px] text-white underline"
        >
          מסך נציג
        </Link>
      ) : null}
      <span className="inline-flex items-center gap-2.5 text-[14px] text-white">
        <span
          aria-hidden="true"
          className="inline-flex h-[34px] w-[34px] items-center justify-center rounded-full bg-royal font-bold"
        >
          {user.name.trim().charAt(0)}
        </span>
        <bdi>{user.name}</bdi>
      </span>
      <Button
        variant="secondary"
        onClick={onLogout}
        className="border-white/30 bg-transparent text-white hover:bg-white/10"
      >
        <Icon name="arrowRight" size={16} />
        יציאה
      </Button>
    </>
  );
}
