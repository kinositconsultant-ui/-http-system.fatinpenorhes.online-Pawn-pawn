import { Link } from "react-router-dom";
import { useLang } from "../../context/LangContext";
import { Car, Bike, Cpu, Smartphone, Truck, ChevronRight } from "lucide-react";

const SERVICES = [
  {
    key: "car",
    Icon: Car,
    img: "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?auto=format&fit=crop&w=900&q=80",
    titleEn: "Car Guarantee",
    titleTet: "Garantia Karreta",
    descEn: "Loans with car, pickup or commercial vehicle as collateral.",
    descTet: "Emprestimu ho garantia karreta privadu, pickup ka veikulu komersial.",
  },
  {
    key: "motorcycle",
    Icon: Bike,
    img: "https://images.unsplash.com/photo-1558981806-ec527fa84c39?auto=format&fit=crop&w=900&q=80",
    titleEn: "Motorcycle Guarantee",
    titleTet: "Garantia Motor",
    descEn: "Use your motorcycle as collateral for a quick loan.",
    descTet: "Motor bele uza hanesan garantia atu hetan osan lalais.",
  },
  {
    key: "computer",
    Icon: Cpu,
    img: "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=900&q=80",
    titleEn: "Computer Guarantee",
    titleTet: "Garantia Komputer",
    descEn: "Laptops, desktops, monitors and other IT equipment.",
    descTet: "Laptop, desktop, monitor no ekipamentu IT seluk.",
  },
  {
    key: "phone",
    Icon: Smartphone,
    img: "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=80",
    titleEn: "Phone Guarantee",
    titleTet: "Garantia Telefone",
    descEn: "Smartphones and tablets can be used as collateral.",
    descTet: "Smartphone no tablet bele sai garantia tuir avaliasaun valor.",
  },
  {
    key: "heavy",
    Icon: Truck,
    img: "https://images.unsplash.com/photo-1591768793355-74d04bb6608f?auto=format&fit=crop&w=900&q=80",
    titleEn: "Heavy Equipment Guarantee",
    titleTet: "Garantia Pezadu",
    descEn: "Forklift, tractor, loader, heavy duty truck — accepted as collateral.",
    descTet: "Forklift, traktór, loader, kamiaun pezadu — simu hanesan garantia.",
  },
];

export default function Services() {
  const { lang } = useLang();
  return (
    <section className="bg-white py-16">
      <div className="max-w-7xl mx-auto px-6 lg:px-10">
        <header className="text-center mb-12">
          <h1 className="font-display text-4xl md:text-5xl font-bold text-[#1A2A52]">
            {lang === "tet" ? "Ami Nia Servisu" : "Our Services"}
          </h1>
          <div className="w-20 h-1 bg-[#F0B435] mx-auto mt-4 rounded-full" />
        </header>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {SERVICES.map((s) => (
            <article
              key={s.key}
              className="rounded-2xl overflow-hidden bg-white border border-stone-200 shadow-sm hover:shadow-lg transition-shadow"
              data-testid={`service-card-${s.key}`}
            >
              <div className="aspect-[16/10] overflow-hidden">
                <img
                  src={s.img}
                  alt={s.key}
                  className="w-full h-full object-cover hover:scale-105 transition-transform duration-300"
                />
              </div>
              <div className="p-5 space-y-3">
                <div className="flex items-center gap-2">
                  <div className="w-9 h-9 rounded-md bg-[#1A2A52] text-white flex items-center justify-center">
                    <s.Icon className="w-5 h-5" />
                  </div>
                  <h3 className="font-display text-xl font-bold text-[#1A2A52]">
                    {lang === "tet" ? s.titleTet : s.titleEn}
                  </h3>
                </div>
                <p className="text-sm text-stone-600">
                  {lang === "tet" ? s.descTet : s.descEn}
                </p>
                <Link
                  to="/contact"
                  className="inline-flex items-center gap-1 text-sm font-semibold text-[#1A2A52] hover:text-[#F0B435]"
                >
                  {lang === "tet" ? "Haree Detallu" : "View Details"} <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
