import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";

/** A card above the chat: the upload fills in most of the details. The button starts the same
 * upload as the paperclip (privacy notice first, once per session). */
export function PayslipOffer({ onUpload }: { onUpload: () => void }) {
  return (
    <section
      aria-labelledby="payslip-offer-title"
      className="mx-5 mt-3 flex flex-wrap items-center gap-3 rounded-tile border border-chip-payslip bg-chip-payslip-bg px-4 py-3"
    >
      <p id="payslip-offer-title" className="min-w-[10rem] flex-1 font-semibold text-navy">
        העלאת תלוש שכר ממלאת את רוב הפרטים
      </p>
      <Button variant="secondary" onClick={onUpload}>
        <Icon name="paperclip" size={16} />
        העלאת תלוש
      </Button>
    </section>
  );
}
