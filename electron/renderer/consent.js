// AllPrime - Primer Tasarim Araci
// Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
//
// GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
// (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
// verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
// AllPrime - acilis bilgilendirme ekrani
// Onay istemez: metin okunabilir, "Anladim, devam et" tek dugmedir. Bildirim ilk acilista ve
// metin surumu (main.js NOTICE_VERSION) degisince bir kez gosterilir; dugmeye basilinca
// yalnizca bildirim surumu ve gosterilme tarihi yerelde kaydedilir.

const $ = (id) => document.getElementById(id);
let LANG = "tr";

const TXT = {
  tr: {
    sub: "Bilgilendirme ve sorumluluk bildirimi",
    langlabel: "Dil / Language",
    lead: "Bu yazılımı kullanmadan önce aşağıdaki bildirimi okumanızı öneririz. Bu ekran " +
          "yalnızca bilgilendirme içindir; onay istemez. Bildirimin gösterildiği bu bilgisayarda kaydedilir.",
    ban: "Önemli uyarılar",
    n1: "AllPrime bir tanı cihazı değildir; ürettiği primerler, tanı amaçlı kullanılmadan önce " +
        "laboratuvarınızda deneysel olarak doğrulanmalıdır.",
    n2: "Yazılım “olduğu gibi”, garantisiz sunulur; kullanımdan doğan sonuçların sorumluluğu " +
        "kullanıcıya aittir.",
    n3: "AllPrime GNU GPL (v2 veya sonrası) ile lisanslıdır; üçüncü taraf lisansları uygulama " +
        "klasöründedir.",
    accept: "Anladım, devam et",
    meta: (v, s) => `Sürüm ${v} · bildirim metni sürümü ${s}`,
    copy: "© 2026 Eren Kılınç · GNU GPL v2 veya sonrası",
    title: "AllPrime",
  },
  en: {
    sub: "Notice and disclaimer",
    langlabel: "Dil / Language",
    lead: "We recommend reading the notice below before using this software. This screen is " +
          "informational only; it does not ask for acceptance. The fact that it was shown is stored on this computer.",
    ban: "Important notices",
    n1: "AllPrime is not a diagnostic device; primers it produces should be experimentally " +
        "validated by your laboratory before any diagnostic use.",
    n2: "The software is provided “as is”, without warranty; responsibility for any outcome " +
        "arising from its use lies with the user.",
    n3: "AllPrime is licensed under the GNU GPL (v2 or later); third-party licences are in the " +
        "application folder.",
    accept: "Got it, continue",
    meta: (v, s) => `Version ${v} · notice version ${s}`,
    copy: "© 2026 Eren Kılınç · GNU GPL v2 or later",
    title: "AllPrime",
  },
};

let INFO = { version: "?", noticeVersion: "?" };

async function init() {
  if (!window.allprime) return;
  INFO = await window.allprime.getAppInfo();
  LANG = INFO.lang || "tr";
  document.querySelectorAll(".lang-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.lang === LANG);
    b.addEventListener("click", () => setLang(b.dataset.lang));
  });
  $("acceptBtn").addEventListener("click", devam);
  await setLang(LANG);
}

async function setLang(lang) {
  LANG = lang;
  document.documentElement.lang = lang;
  document.querySelectorAll(".lang-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.lang === lang));
  const t = TXT[lang];
  $("c_sub").textContent = t.sub;
  $("c_langlabel").textContent = t.langlabel;
  $("c_lead").textContent = t.lead;
  $("c_ban").textContent = t.ban;
  $("c_n1").textContent = t.n1;
  $("c_n2").textContent = t.n2;
  $("c_n3").textContent = t.n3;
  $("acceptBtn").textContent = t.accept;
  $("c_copy").textContent = t.copy;
  $("c_meta").textContent = t.meta(INFO.version, INFO.noticeVersion);
  $("termsBox").innerHTML = await window.allprime.getTerms(lang);
  $("termsBox").scrollTop = 0;
}

async function devam() {
  $("acceptBtn").disabled = true;
  await window.allprime.ackNotice(LANG);
}

init();
