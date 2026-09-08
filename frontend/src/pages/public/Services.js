import { Link } from "react-router-dom";
import { useLang } from "../../context/LangContext";
import { Car, Bike, Cpu, Smartphone, Truck, ChevronRight } from "lucide-react";
import { usePublicSite } from "../../lib/publicSite";

const B = "https://static.prod-images.emergentagent.com/jobs/7e09fb06-54ad-4312-b74c-802a3b1278f0/images/";
const FALLBACK = {
  svc_car: B + "e633ef5e6f6d6d454979d04345aa1eed8e32225eade03a03369e917d8a379137.jpeg",
  svc_moto: B + "f76936e0dbf1b0f6ea8721c18c619bfb20a8b4329a4c804c71f5765cd2cae09a.jpeg",
  svc_computer: B + "aad732dbf737126e6231fe8b5d8cc72a81b99bba5d9cf773a2dc7d0e01ec4d32.jpeg",
  svc_phone: B + "bd0d725633a5579b25120b06b43458a0f65831d691ee2443f13e37b202400246.jpeg",
  svc_heavy: B + "88986dcba32a527b73873383392c31b04f4d4bcccb33641e794123ffc04b2dbc.jpeg",
};

const SERVICES = [
  {
    key: "car",
    slot: "svc_car",
    Icon: Car,
    titleEn: "Car Guarantee",
    titleTet: "Garantia Karreta",
    descEn: "Loans with car, pickup or commercial vehicle as collateral.",
    descTet: "Emprestimu ho garantia karreta privadu, pickup ka veikulu komersial.",
  },
  {
    key: "motorcycle",
    slot: "svc_moto",
    Icon: Bike,
    titleEn: "Motorcycle Guarantee",
    titleTet: "Garantia Motor",
    descEn: "Use your motorcycle as collateral for a quick loan.",
    descTet: "Motor bele uza hanesan garantia atu hetan osan lalais.",
  },
  {
    key: "computer",
    slot: "svc_computer",
    Icon: Cpu,
    titleEn: "Computer Guarantee",
    titleTet: "Garantia Komputer",
    descEn: "Laptops, desktops, monitors and other IT equipment.",
    descTet: "Laptop, desktop, monitor no ekipamentu IT seluk.",
  },
  {
    key: "phone",
    slot: "svc_phone",
    Icon: Smartphone,
    titleEn: "Phone Guarantee",
    titleTet: "Garantia Telefone",
    descEn: "Smartphones and tablets can be used as collateral.",
    descTet: "Smartphone no tablet bele sai garantia tuir avaliasaun valor.",
  },
  {
    key: "heavy",
    slot: "svc_heavy",
    Icon: Truck,
    titleEn: "Heavy Equipment Guarantee",
    titleTet: "Garantia Pezadu",
    descEn: "Forklift, tractor, loader, heavy duty truck — accepted as collateral.",
    descTet: "Forklift, traktór, loader, kamiaun pezadu — simu hanesan garantia.",
  },
];

export default function Services() {
  const { lang } = useLang();
  const { images } = usePublicSite();
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
                  src={images[s.slot] || FALLBACK[s.slot]}
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
