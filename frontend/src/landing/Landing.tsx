import { Link } from "react-router-dom";
import mark from "../assets/compass-mark.png";
import { Icon } from "../ui/icons";
import { DemoCard } from "./DemoCard";
import { LoginForm } from "./LoginForm";
import "./landing.css";

/** The compass mark in a white circle, a pulsing halo and two slowly turning rings. */
function Logo() {
  return (
    <div className="lp-rise relative flex aspect-square w-[340px] max-w-[86vw] items-center justify-center">
      <div
        aria-hidden="true"
        className="lp-halo absolute inset-[8%] rounded-full bg-[radial-gradient(circle,color-mix(in_srgb,var(--color-knob-on)_55%,transparent)_0%,transparent_68%)]"
      />
      <svg
        aria-hidden="true"
        className="lp-ring absolute inset-0 h-full w-full"
        viewBox="0 0 340 340"
      >
        <circle
          cx="170"
          cy="170"
          r="164"
          fill="none"
          stroke="var(--color-knob-on)"
          strokeOpacity=".55"
          strokeWidth="1.5"
          strokeDasharray="2 9"
        />
        <path
          d="M170 2v14M170 324v14M2 170h14M324 170h14"
          stroke="var(--color-mist)"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
      <svg
        aria-hidden="true"
        className="lp-ring2 absolute inset-[9%] h-[82%] w-[82%]"
        viewBox="0 0 340 340"
      >
        <circle cx="170" cy="170" r="166" fill="none" stroke="#fff" strokeOpacity=".18" />
        <path d="M170 4l6 14h-12z" fill="var(--color-engine-tool)" />
      </svg>
      <div className="relative flex aspect-square w-[62%] items-center justify-center rounded-full bg-white shadow-[0_0_0_10px_rgba(255,255,255,0.06),0_30px_80px_rgba(0,0,0,0.45)]">
        <img src={mark} alt="Compass, יועץ הרכב של שטראוס" className="h-auto w-[74%]" />
      </div>
    </div>
  );
}

const STEPS = [
  {
    n: "1",
    title: "המודל מציע",
    body: "מבין מה שואלים, אוסף את הנתונים החסרים ובוחר באיזה כלי להשתמש.",
    tone: "bg-chip-occupation-bg text-chip-occupation",
  },
  {
    n: "2",
    title: "הכלים מחשבים",
    body: "נוסחה קבועה לפי כללי החברה, חישוב עשרוני מדויק בלי עיגול בדרך, ומקור לכל ערך.",
    tone: "bg-up-bg text-up-ink",
  },
] as const;

const FEATURES = [
  {
    icon: "check" as const,
    title: "כל מספר עם מקור",
    body: "לחיצה על עמודה במפל מראה מאיפה הגיע הסכום: מהתלוש, מהעיסוק, מהנציג או ממה שסיפרת.",
    tone: "bg-chip-employee-bg text-royal",
  },
  {
    icon: "book" as const,
    title: "תלוש בשנייה",
    body: "מעלים תלוש, מאשרים את מה שנקרא ממנו, וממשיכים. התלוש לא נשמר.",
    tone: "bg-up-bg text-up-ink",
  },
  {
    icon: "clock" as const,
    title: "נציג בלחיצה",
    body: "כשחסר נתון שרק החברה יודעת, נפתחת פנייה לנציג, והתוצאה מתעדכנת מעצמה כשהוא עונה.",
    tone: "bg-chip-pending-bg text-chip-pending",
  },
];

/** `/` for a visitor who is not logged in (COMPASS_AUTH=1): the product, a live demo card and the
 * login. Layout, copy and motion follow briefs/design/Landing.reference.html. */
export function Landing() {
  return (
    <div className="bg-engine-code text-engine-text">
      <section aria-label="פתיחה" className="lp-hero relative px-6 pt-7 pb-[120px] max-sm:pb-16">
        <nav
          aria-label="ניווט"
          className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-4"
        >
          <div className="flex items-center gap-3">
            <span className="inline-flex rounded-[12px] bg-white p-[5px]">
              <img src={mark} alt="" className="h-[34px] w-auto" />
            </span>
            <span className="ltr text-[18px] font-bold tracking-[0.06em]">COMPASS</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href="#how"
              className="inline-flex min-h-11 items-center rounded-control px-3.5 text-[15px] text-engine-guard hover:text-white"
            >
              איך זה עובד
            </a>
            <a
              href="#login"
              className="inline-flex min-h-11 items-center rounded-control border border-white/30 px-[18px] text-[15px] font-semibold text-white hover:bg-white/10"
            >
              כניסה לעובדים
            </a>
          </div>
        </nav>

        <main className="mx-auto flex max-w-[1240px] flex-col items-center gap-7 pt-[72px] text-center max-sm:pt-8">
          <Logo />
          <div className="lp-rise flex flex-col items-center gap-2.5 [animation-delay:0.15s]">
            <span className="ltr text-[clamp(48px,8vw,96px)] leading-none font-bold tracking-[0.08em] text-white">
              COMPASS
            </span>
            <span className="text-[clamp(20px,2.4vw,28px)] font-medium text-mist">
              יועץ הרכב של שטראוס
            </span>
          </div>
          <h1 className="lp-rise mt-3 max-w-[820px] text-[clamp(30px,4vw,52px)] leading-[1.2] font-bold text-white [animation-delay:0.3s]">
            כך תוכלו לדעת בדיוק כמה נשאר בנטו,
            <br />
            לפני שבוחרים רכב.
          </h1>
          <p className="lp-rise max-w-[640px] text-[19px] leading-relaxed text-soft [animation-delay:0.4s]">
            שיחה אחת בעברית, תלוש אחד, ותוצאה מדויקת עד השקל, עם מקור לכל מספר.
          </p>

          <div
            id="login"
            className="mt-[72px] grid w-full scroll-mt-6 grid-cols-1 items-stretch justify-center gap-8 text-start max-sm:mt-6 min-[700px]:grid-cols-[minmax(0,600px)_minmax(0,440px)]"
          >
            {/* on a phone the login comes first, then the demo: the DOM order; from 700px the demo
                is the first column (the right one in RTL) */}
            <div className="min-w-0 min-[700px]:order-2">
              <LoginForm />
            </div>
            <div className="min-w-0 min-[700px]:order-1">
              <DemoCard />
            </div>
          </div>
        </main>
      </section>

      <section
        id="how"
        aria-label="איך זה עובד"
        className="bg-ground px-6 py-[110px] text-ink max-sm:py-16"
      >
        <div className="mx-auto flex max-w-[1240px] flex-col gap-14">
          <div className="flex flex-col items-center gap-3.5 text-center">
            <span className="text-[14px] font-semibold tracking-[0.08em] text-royal">
              איך זה עובד
            </span>
            <h2 className="text-[clamp(30px,3.4vw,44px)] leading-[1.2] font-bold text-navy">
              המודל לא מחשב כסף. אף פעם.
            </h2>
            <p className="max-w-[660px] text-[18px] leading-relaxed text-muted">
              הבינה המלאכותית מנהלת את השיחה. החישוב עצמו נעשה בקוד מדויק, וכל מספר נבדק לפני
              שהוא מגיע אליך.
            </p>
          </div>
          <ol className="grid grid-cols-[repeat(auto-fit,minmax(min(260px,100%),1fr))] gap-5">
            {STEPS.map((step) => (
              <li
                key={step.n}
                className="flex flex-col gap-3.5 rounded-[20px] border border-line bg-surface p-7"
              >
                <span
                  aria-hidden="true"
                  className={`flex h-[52px] w-[52px] items-center justify-center rounded-[16px] text-[22px] font-bold ${step.tone}`}
                >
                  {step.n}
                </span>
                <h3 className="text-[22px] font-bold text-navy">{step.title}</h3>
                <p className="text-[16px] leading-relaxed text-muted">{step.body}</p>
              </li>
            ))}
            <li className="flex flex-col gap-3.5 rounded-[20px] bg-navy p-7 text-white">
              <span
                aria-hidden="true"
                className="flex h-[52px] w-[52px] items-center justify-center rounded-[16px] bg-royal"
              >
                <Icon name="shield" size={26} />
              </span>
              <h3 className="text-[22px] font-bold">השומר בודק</h3>
              <p className="text-[16px] leading-relaxed text-soft">
                כל מספר בתשובה חייב להגיע מכלי, מהעובד/ת או מהנציג. מספר בלי מקור לא יוצא.
              </p>
            </li>
          </ol>
        </div>
      </section>

      <section aria-label="מה מקבלים" className="bg-surface px-6 py-[110px] text-ink max-sm:py-16">
        <ul className="mx-auto grid max-w-[1240px] grid-cols-[repeat(auto-fit,minmax(min(300px,100%),1fr))] gap-x-10 gap-y-12">
          {FEATURES.map((feature) => (
            <li key={feature.title} className="flex flex-col gap-3.5">
              <span
                aria-hidden="true"
                className={`flex h-14 w-14 items-center justify-center rounded-[16px] ${feature.tone}`}
              >
                <Icon name={feature.icon} size={26} />
              </span>
              <h3 className="text-[24px] font-bold text-navy">{feature.title}</h3>
              <p className="text-[17px] leading-relaxed text-muted">{feature.body}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="קריאה לפעולה" className="lp-cta px-6 pt-[110px] pb-[72px] max-sm:pt-16">
        <div className="mx-auto flex max-w-[1240px] flex-col items-center gap-6 text-center">
          <h2 className="text-[clamp(30px,3.4vw,44px)] leading-[1.2] font-bold text-white">
            מוכנים לבדוק?
          </h2>
          <a
            href="#login"
            className="inline-flex min-h-14 items-center justify-center rounded-[14px] bg-royal px-[34px] text-[18px] font-semibold text-white hover:bg-royal-hover"
          >
            כניסה לעובדים
          </a>
          <div className="flex items-center gap-2.5 text-[15px] text-soft">
            <span className="text-engine-tool">
              <Icon name="shield" size={18} />
            </span>
            הנתונים שלך נשארים שלך. התלוש לא נשמר, ואיש מלבדך לא רואה את השיחות.
          </div>
          <div className="mt-10 h-px w-full bg-white/10" />
          <div className="flex w-full flex-wrap items-center justify-between gap-4 text-[14px] text-faint">
            <div className="flex items-center gap-2.5">
              <span className="inline-flex rounded-[10px] bg-white p-1">
                <img src={mark} alt="" className="h-[26px] w-auto" />
              </span>
              <span className="font-semibold text-engine-text">יועץ הרכב של שטראוס</span>
            </div>
            <span>פותח במסגרת האתגר של קבוצת שטראוס</span>
            <Link to="/register" className="text-engine-guard underline hover:text-white">
              הרשמה עם קוד הזמנה
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
