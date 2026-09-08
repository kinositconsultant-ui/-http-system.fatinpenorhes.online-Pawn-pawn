import ReviewForm from "../../components/public/ReviewForm";
import { useLang } from "../../context/LangContext";

export default function Review() {
  const { t } = useLang();
  return (
    <section className="max-w-3xl mx-auto px-6 lg:px-10 py-16" data-testid="review-page">
      <div className="text-[11px] uppercase tracking-[0.28em] font-semibold text-[#C17767] mb-3">{t("home_testimonials_eyebrow")}</div>
      <h1 className="font-display text-4xl sm:text-5xl text-stone-900 mb-8">{t("leave_review")}</h1>
      <ReviewForm />
    </section>
  );
}
