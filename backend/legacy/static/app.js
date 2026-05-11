const STORAGE_KEY = "basalam-product-importer:v1";
const DEFAULT_PRODUCT_STATUS = "2976";
const DEFAULT_IMAGE_MODEL = "google/gemini-2.5-flash-image";
const PRICE_UNIT = "toman";
const PRICE_UNIT_LABEL = "تومان";
const RIALS_PER_TOMAN = 10;
const CATEGORY_SCHEMA_VERSION = 2;

const FIXED_HEADERS = [
  "عملیات",
  "عکس محصول",
  "وضعیت",
  "دسته‌بندی",
  "نام محصول",
  "معرفی کوتاه",
  "توضیحات",
  "قیمت",
  "موجودی",
  "وزن",
  "واحد فروش",
  "زمان ارسال",
  "تنوع‌ها",
  "شناسه",
];

const UNIT_TYPES = [
  { id: "", title: "انتخاب کنید" },
  { id: 6375, title: "مترمربع" },
  { id: 6374, title: "میلی‌متر" },
  { id: 6373, title: "جلد" },
  { id: 6332, title: "فوت" },
  { id: 6331, title: "اینچ" },
  { id: 6330, title: "سیر" },
  { id: 6329, title: "اصله" },
  { id: 6328, title: "کلاف" },
  { id: 6327, title: "قالب" },
  { id: 6326, title: "شاخه" },
  { id: 6325, title: "بوته" },
  { id: 6324, title: "دست" },
  { id: 6323, title: "بطری" },
  { id: 6322, title: "تخته" },
  { id: 6321, title: "کارتن" },
  { id: 6320, title: "توپ" },
  { id: 6319, title: "بسته" },
  { id: 6318, title: "جفت" },
  { id: 6317, title: "جین" },
  { id: 6316, title: "طاقه" },
  { id: 6315, title: "قواره" },
  { id: 6314, title: "انس" },
  { id: 6313, title: "سی‌سی" },
  { id: 6312, title: "میلی‌لیتر" },
  { id: 6311, title: "لیتر" },
  { id: 6310, title: "تکه" },
  { id: 6309, title: "مثقال" },
  { id: 6308, title: "سانتی‌متر" },
  { id: 6307, title: "متر" },
  { id: 6306, title: "گرم" },
  { id: 6305, title: "کیلوگرم" },
  { id: 6304, title: "عددی" },
  { id: 6392, title: "رول" },
  { id: 6438, title: "سوت" },
  { id: 6466, title: "قیراط" },
];
const VALID_UNIT_TYPE_IDS = new Set(UNIT_TYPES.filter((item) => item.id).map((item) => String(item.id)));
const CATEGORY_UNIT_TYPE_ID_ALIASES = new Map([
  ["5060", "6306"], // گرم در خروجی دسته‌ها
  ["5130", "6305"], // کیلوگرم در خروجی دسته‌ها
  ["5135", "6312"], // میلی‌لیتر در خروجی دسته‌ها
]);
const GRAM_UNIT_TYPE_ID = 6306;
const KILOGRAM_UNIT_TYPE_ID = 6305;
const COUNT_UNIT_TYPE_ID = 6304;
const MEASURED_QUANTITY_UNIT_TYPE_IDS = new Set([GRAM_UNIT_TYPE_ID, KILOGRAM_UNIT_TYPE_ID, 6311, 6312, 6313]);
const MOBILE_BREAKPOINT_QUERY = "(max-width: 720px)";
const MOBILE_STEPS = [
  { id: "media", title: "عکس و تحلیل" },
  { id: "basics", title: "اطلاعات اصلی" },
  { id: "details", title: "جزئیات" },
  { id: "review", title: "بازبینی" },
];

const state = {
  settings: {
    basalamToken: "",
    openRouterKey: "",
    openRouterModel: "google/gemini-2.5-flash",
    openRouterImageModel: DEFAULT_IMAGE_MODEL,
    vendorId: "",
    defaultStock: "1",
    defaultPreparationDays: "3",
  },
  categories: [],
  rows: [],
  attributesByCategory: {},
  priceUnit: PRICE_UNIT,
  categorySchemaVersion: CATEGORY_SCHEMA_VERSION,
};

const mobileState = {
  activeRowId: "",
  step: 0,
};

const els = {
  settingsPanel: document.getElementById("settingsPanel"),
  basalamToken: document.getElementById("basalamToken"),
  openRouterKey: document.getElementById("openRouterKey"),
  openRouterModel: document.getElementById("openRouterModel"),
  openRouterImageModel: document.getElementById("openRouterImageModel"),
  vendorId: document.getElementById("vendorId"),
  defaultStock: document.getElementById("defaultStock"),
  defaultPreparationDays: document.getElementById("defaultPreparationDays"),
  saveSettingsBtn: document.getElementById("saveSettingsBtn"),
  verifyTokenBtn: document.getElementById("verifyTokenBtn"),
  loadCategoriesBtn: document.getElementById("loadCategoriesBtn"),
  clearDataBtn: document.getElementById("clearDataBtn"),
  imageInput: document.getElementById("imageInput"),
  statusLine: document.getElementById("statusLine"),
  tableHead: document.getElementById("tableHead"),
  tableBody: document.getElementById("tableBody"),
  mobileWorkflow: document.getElementById("mobileWorkflow"),
  mobileQueue: document.getElementById("mobileQueue"),
  mobileWizard: document.getElementById("mobileWizard"),
  categoryOptions: document.getElementById("categoryOptions"),
  submitDialog: document.getElementById("submitDialog"),
  payloadPreview: document.getElementById("payloadPreview"),
  confirmSubmitBtn: document.getElementById("confirmSubmitBtn"),
  imagePreviewDialog: document.getElementById("imagePreviewDialog"),
  imagePreviewTitle: document.getElementById("imagePreviewTitle"),
  imagePreviewMeta: document.getElementById("imagePreviewMeta"),
  imagePreviewImg: document.getElementById("imagePreviewImg"),
  previewSelectedBtn: document.getElementById("previewSelectedBtn"),
  previewEnhancedBtn: document.getElementById("previewEnhancedBtn"),
  previewOriginalBtn: document.getElementById("previewOriginalBtn"),
};

let pendingSubmitRowId = null;
const mobileMedia = window.matchMedia(MOBILE_BREAKPOINT_QUERY);
let syncingSettingsPanel = false;
let settingsPanelTouched = false;

function setStatus(message) {
  els.statusLine.textContent = message;
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return;
  let migratedPrices = false;
  let migratedRows = false;
  try {
    const parsed = JSON.parse(raw);
    Object.assign(state.settings, parsed.settings || {});
    state.categories =
      parsed.categorySchemaVersion === CATEGORY_SCHEMA_VERSION && Array.isArray(parsed.categories)
        ? parsed.categories
        : [];
    state.rows = Array.isArray(parsed.rows) ? parsed.rows : [];
    state.attributesByCategory = parsed.attributesByCategory || {};
    if ((parsed.priceUnit || "rial") !== PRICE_UNIT) {
      state.rows.forEach(migrateRowPricesToToman);
      migratedPrices = true;
    }
    state.priceUnit = PRICE_UNIT;
    state.categorySchemaVersion = CATEGORY_SCHEMA_VERSION;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
  for (const row of state.rows) {
    normalizeRowImages(row);
    migratedRows = applyCategoryUnit(row) || migratedRows;
    const previousPackageWeight = row.package_weight;
    applyEstimatedPackageWeight(row, {});
    migratedRows = migratedRows || previousPackageWeight !== row.package_weight;
    if (row.category_id && state.categories.length) {
      const previousUnitType = row.unit_type;
      const previousUnitQuantity = row.unit_quantity;
      applySaleUnit(row, {});
      migratedRows = migratedRows || previousUnitType !== row.unit_type || previousUnitQuantity !== row.unit_quantity;
    }
    row.general_errors = Array.isArray(row.general_errors) ? row.general_errors : [];
    row.errors = validateRow(row);
    if (!["Submitted", "Submitting", "Failed"].includes(row.status)) {
      row.status = row.errors.length ? "Needs Review" : "Ready";
    }
  }
  delete state.settings.defaultPackageWeight;
  delete state.settings.defaultStatus;
  delete state.settings.defaultWholesale;
  if (migratedPrices || migratedRows) saveState();
}

function syncSettingsToForm() {
  for (const [key, value] of Object.entries(state.settings)) {
    const element = els[key];
    if (!element) continue;
    if (element.type === "checkbox") {
      element.checked = Boolean(value);
    } else {
      element.value = value ?? "";
    }
  }
}

function syncSettingsFromForm() {
  for (const key of Object.keys(state.settings)) {
    const element = els[key];
    if (!element) continue;
    state.settings[key] = element.type === "checkbox" ? element.checked : element.value.trim();
  }
  saveState();
}

async function apiFetch(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = { detail: { message: await response.text() } };
  }
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail : detail?.message || "درخواست ناموفق بود.";
    const error = new Error(message);
    error.status = response.status;
    error.detail = detail;
    throw error;
  }
  return body;
}

function statusClass(status) {
  return String(status || "")
    .toLowerCase()
    .replaceAll(" ", "-");
}

function statusLabel(status) {
  const labels = {
    "Image Added": "عکس اضافه شد",
    Analyzing: "در حال تحلیل",
    "Needs Review": "نیاز به تکمیل",
    Ready: "آماده ثبت",
    Submitting: "در حال ثبت",
    Submitted: "ثبت شد",
    Failed: "ناموفق",
  };
  return labels[status] || status || "عکس اضافه شد";
}

function hasCompletedAnalysis(row) {
  return Boolean(
    Number(row.analysis_runs || 0) > 0 ||
      row.analyzed_at ||
      row.category_id ||
      row.name ||
      row.brief ||
      row.description ||
      row.price_suggested ||
      (Array.isArray(row.price_samples) && row.price_samples.length)
  );
}

function analyzeButtonText(row) {
  if (row.status === "Analyzing") return "در حال تحلیل";
  return hasCompletedAnalysis(row) ? "تحلیل مجدد" : "شروع تحلیل";
}

function analyzeButtonClass(row) {
  return hasCompletedAnalysis(row) ? "mini" : "mini primary";
}

function uid() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function priceValueToToman(value) {
  const numeric = numberOrNull(value);
  if (numeric === null) return value || "";
  return String(Math.round(numeric / RIALS_PER_TOMAN));
}

function priceSampleValueToToman(value) {
  const numeric = numberOrNull(value);
  if (numeric === null) return value ?? null;
  return Math.round(numeric / RIALS_PER_TOMAN);
}

function migrateRowPricesToToman(row) {
  for (const key of ["price_suggested", "price_final", "price_min", "price_max"]) {
    row[key] = priceValueToToman(row[key]);
  }
  if (Array.isArray(row.price_samples)) {
    for (const sample of row.price_samples) {
      for (const key of ["price", "used_price", "comparable_price"]) {
        if (key in sample) sample[key] = priceSampleValueToToman(sample[key]);
      }
    }
  }
  if (Array.isArray(row.variants)) {
    for (const variant of row.variants) {
      if ("primary_price" in variant) variant.primary_price = priceValueToToman(variant.primary_price);
    }
  }
}

function formatPrice(value) {
  const numeric = numberOrNull(value);
  if (numeric === null) return "";
  return `${numeric.toLocaleString("fa-IR")} ${PRICE_UNIT_LABEL}`;
}

function packageWeightForRow(row) {
  const weight = numberOrNull(row.weight);
  const packageWeight = numberOrNull(row.package_weight);
  if (weight === null) return packageWeight;
  if (packageWeight === null || packageWeight <= weight) return Math.ceil(weight + 1);
  return packageWeight;
}

function inferredPackageWeight(weight) {
  const numeric = numberOrNull(weight);
  if (numeric === null) return null;
  const extra = Math.max(20, Math.min(150, numeric * 0.12));
  return Math.ceil(numeric + extra);
}

function normalizeText(value) {
  return String(value || "")
    .replaceAll("ي", "ی")
    .replaceAll("ك", "ک")
    .replaceAll("‌", "")
    .replaceAll(" ", "")
    .trim();
}

function validUnitType(value) {
  if (value === "" || value === null || value === undefined) return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  const unitTypeId = CATEGORY_UNIT_TYPE_ID_ALIASES.get(String(numeric)) || String(numeric);
  return VALID_UNIT_TYPE_IDS.has(unitTypeId) ? Number(unitTypeId) : null;
}

function canonicalUnitType(value) {
  const unitType = validUnitType(value);
  return unitType ? String(unitType) : "";
}

function normalizedUnitQuantity(value) {
  const numeric = numberOrNull(value);
  if (numeric === null || numeric <= 0) return "";
  const rounded = Math.round(numeric * 100) / 100;
  return String(Number.isInteger(rounded) ? Math.round(rounded) : rounded);
}

function analysisObject(...values) {
  return values.find((value) => value && typeof value === "object" && !Array.isArray(value)) || {};
}

function confidenceValue(value) {
  const numeric = Number(value || 0);
  return Number.isFinite(numeric) ? numeric : 0;
}

function weightValueInGrams(weight) {
  const value = numberOrNull(weight?.value ?? weight?.quantity ?? weight);
  if (value === null || value <= 0) return null;
  const unit = normalizeText(weight?.unit || weight?.unit_title || weight?.title || "gram").toLowerCase();
  if (unit.includes("kilogram") || unit.includes("kg") || unit.includes("کیلو")) return value * 1000;
  return value;
}

function unitTypeFromCategory(category) {
  const unit = category?.unit_type ?? category?.unitType ?? category?.unit_type_id ?? category?.unitTypeId;
  const directUnitType = validUnitType(unit);
  if (directUnitType) return String(directUnitType);
  if (!unit || typeof unit !== "object") return "";

  const candidateIds = [unit.id, unit.value, unit.unit_type, unit.unitType, unit.unit_type_id, unit.unitTypeId];
  for (const candidate of candidateIds) {
    const unitType = validUnitType(candidate);
    if (unitType) return String(unitType);
  }

  const normalizedTitle = normalizeText(unit.title || unit.name || unit.label || unit.value);
  const match = UNIT_TYPES.find((item) => normalizeText(item.title) === normalizedTitle);
  return match?.id ? String(match.id) : "";
}

function applyCategoryUnit(row, category = categoryById(row?.category_id)) {
  if (!row) return false;
  const existingUnitType = canonicalUnitType(row.unit_type);
  if (existingUnitType) {
    if (String(row.unit_type) !== existingUnitType) {
      row.unit_type = existingUnitType;
      return true;
    }
    return false;
  }
  const unitType = unitTypeFromCategory(category);
  if (!unitType) return false;
  row.unit_type = unitType;
  return true;
}

function applyCategoryUnitsToRows() {
  let changed = false;
  for (const row of state.rows) {
    if (!row.category_id) continue;
    changed = applyCategoryUnit(row) || changed;
    const previousUnitType = row.unit_type;
    const previousUnitQuantity = row.unit_quantity;
    const previousPackageWeight = row.package_weight;
    applyEstimatedPackageWeight(row, {});
    applySaleUnit(row, {});
    changed =
      changed ||
      previousUnitType !== row.unit_type ||
      previousUnitQuantity !== row.unit_quantity ||
      previousPackageWeight !== row.package_weight;
  }
  return changed;
}

function applyEstimatedPackageWeight(row, analysis) {
  if (numberOrNull(row.package_weight) !== null) return;
  const packageWeight = analysisObject(
    analysis?.estimated_package_weight,
    analysis?.package_weight,
    analysis?.estimated_packaged_weight
  );
  const inferredByAi = weightValueInGrams(packageWeight);
  const netWeight = numberOrNull(row.weight);
  if (inferredByAi !== null && confidenceValue(packageWeight.confidence) >= 0.45) {
    row.package_weight = String(Math.ceil(netWeight !== null ? Math.max(inferredByAi, netWeight + 1) : inferredByAi));
    return;
  }
  const inferred = inferredPackageWeight(netWeight);
  if (inferred !== null) row.package_weight = String(inferred);
}

function saleUnitFromAnalysis(analysis) {
  const unit = analysisObject(analysis?.sale_unit, analysis?.saleUnit, analysis?.unit);
  return {
    quantity: unit.quantity ?? unit.unit_quantity ?? unit.value,
    unitType: unit.unit_type ?? unit.unitType ?? unit.unit_type_id,
    confidence: confidenceValue(unit.confidence),
  };
}

function applySaleUnit(row, analysis) {
  const saleUnit = saleUnitFromAnalysis(analysis);
  const analysisUnitType = validUnitType(saleUnit.unitType);
  const existingUnitType = canonicalUnitType(row.unit_type);
  if (existingUnitType) row.unit_type = existingUnitType;
  else if (analysisUnitType) row.unit_type = String(analysisUnitType);
  else row.unit_type = String(COUNT_UNIT_TYPE_ID);

  const unitType = validUnitType(row.unit_type);
  if (!unitType || numberOrNull(row.unit_quantity) !== null) return;

  const analysisQuantity = numberOrNull(saleUnit.quantity);
  if (analysisQuantity !== null && saleUnit.confidence >= 0.45) {
    row.unit_quantity = normalizedUnitQuantity(analysisQuantity);
    return;
  }

  const netWeight = numberOrNull(row.weight);
  if (unitType === GRAM_UNIT_TYPE_ID && netWeight !== null) {
    row.unit_quantity = normalizedUnitQuantity(netWeight);
  } else if (unitType === KILOGRAM_UNIT_TYPE_ID && netWeight !== null) {
    row.unit_quantity = normalizedUnitQuantity(netWeight / 1000);
  } else if (!MEASURED_QUANTITY_UNIT_TYPE_IDS.has(unitType)) {
    row.unit_quantity = "1";
  }
}

function splitIds(value) {
  return String(value || "")
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item) && item > 0);
}

function categoryById(categoryId) {
  return state.categories.find((category) => String(category.id) === String(categoryId));
}

function updateCategoryOptions() {
  els.categoryOptions.innerHTML = "";
  const fragment = document.createDocumentFragment();
  for (const category of state.categories.filter((item) => item.is_leaf)) {
    const option = document.createElement("option");
    option.value = `${category.id} - ${category.path || category.title}`;
    fragment.appendChild(option);
  }
  els.categoryOptions.appendChild(fragment);
}

function parseCategoryInput(value) {
  const match = String(value || "").match(/^(\d+)/);
  if (!match) return null;
  const category = categoryById(match[1]);
  if (!category) return null;
  return category;
}

function flatAttributesForCategory(categoryId) {
  const payload = state.attributesByCategory[String(categoryId)];
  if (!payload) return [];
  const groups = Array.isArray(payload.data) ? payload.data : [];
  return groups.flatMap((group) => (Array.isArray(group.attributes) ? group.attributes : []));
}

function isRequiredAttribute(attr) {
  return Boolean(attr?.required || attr?.is_required || attr?.isRequired);
}

function requiredAttributesForCategory(categoryId) {
  return flatAttributesForCategory(categoryId).filter(isRequiredAttribute);
}

function dynamicAttributeIds() {
  const ids = new Map();
  for (const row of state.rows) {
    for (const attr of requiredAttributesForCategory(row.category_id)) {
      ids.set(String(attr.id), attr);
    }
  }
  return Array.from(ids.values());
}

function setRowStatusFromValidation(row) {
  const errors = validateRow(row);
  row.errors = errors;
  if (row.status === "Submitting") return;
  row.status = errors.length ? "Needs Review" : "Ready";
}

function validateRow(row) {
  const errors = [];
  row.field_errors = {};
  const addError = (field, message) => {
    errors.push(message);
    row.field_errors[field] = row.field_errors[field] || [];
    row.field_errors[field].push(message);
  };
  if (!row.name) addError("name", "نام محصول را وارد کنید.");
  if (!row.category_id) addError("category", "دسته‌بندی را انتخاب کنید.");
  if (!numberOrNull(row.price_final)) addError("price", "قیمت فروش را وارد کنید.");
  if (numberOrNull(row.stock) === null) addError("stock", "موجودی را وارد کنید.");
  if (packageWeightForRow(row) === null) {
    addError("package_weight", "وزن با بسته‌بندی را وارد کنید.");
  }
  const unitQuantity = numberOrNull(row.unit_quantity);
  const unitType = validUnitType(row.unit_type);
  if ((unitQuantity !== null || row.unit_type) && (unitQuantity === null || !unitType)) {
    addError("unit", "مقدار و واحد فروش را کامل کنید.");
  }
  for (const [index, variant] of normalizedVariants(row).entries()) {
    if (variant.primary_price === null) addError("variants", `قیمت تنوع ${index + 1} را وارد کنید.`);
    if (variant.stock === null) addError("variants", `موجودی تنوع ${index + 1} را وارد کنید.`);
    if (!variant.properties.length) addError("variants", `برای تنوع ${index + 1} حداقل یک ویژگی وارد کنید.`);
    for (const property of variant.properties) {
      if (!property.property || !property.value) {
        addError("variants", `ویژگی و مقدار تنوع ${index + 1} را کامل کنید.`);
      }
    }
  }
  if (!selectedImage(row)) addError("image", "عکس محصول را اضافه کنید.");
  for (const attr of requiredAttributesForCategory(row.category_id)) {
    if (!row.attributes?.[attr.id]) {
      addError(`attribute:${attr.id}`, `ویژگی «${attr.title}» را وارد کنید.`);
    }
  }
  return errors;
}

function providerFieldKey(field) {
  const value = String(field || "");
  const map = {
    package_weight: "package_weight",
    packaged_weight: "package_weight",
    unit_type: "unit",
    unit_quantity: "unit",
    primary_price: "price",
    price: "price",
    stock: "stock",
    inventory: "stock",
    name: "name",
    title: "name",
    category_id: "category",
    photo: "image",
    photos: "image",
    variants: "variants",
  };
  if (value.startsWith("product_attribute") || value.startsWith("attributes")) return "attributes";
  return map[value] || "";
}

function providerErrorItems(detail) {
  const provider = detail?.provider_detail || detail;
  const candidates = [provider?.messages, provider?.openapi_raw_data, provider?.errors, provider?.detail];
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) return candidate.filter((item) => item && typeof item === "object");
  }
  return [];
}

function applyProviderErrors(row, error) {
  row.field_errors = row.field_errors || {};
  row.errors = Array.isArray(row.errors) ? row.errors : [];
  const general = [];
  let mappedCount = 0;
  for (const item of providerErrorItems(error.detail)) {
    const message = item.message || item.msg || error.message;
    const fields = Array.isArray(item.fields) ? item.fields : [];
    const keys = [...new Set(fields.map(providerFieldKey).filter(Boolean))];
    if (!keys.length) {
      general.push(message);
      continue;
    }
    for (const key of keys) {
      row.field_errors[key] = row.field_errors[key] || [];
      row.field_errors[key].push(message);
      row.errors.push(message);
      mappedCount += 1;
    }
  }
  if (!mappedCount && !general.length) general.push(error.message);
  row.general_errors = [...new Set(general)];
}

function normalizeRowImages(row) {
  if (!Array.isArray(row.images)) row.images = [];
  if (!row.images.length && (row.original_image || row.enhanced_image)) {
    row.images.push({
      id: uid(),
      filename: row.filename || "product.jpg",
      original_image: row.original_image || row.enhanced_image,
      enhanced_image: row.enhanced_image || row.original_image,
      use_enhanced: row.use_enhanced !== false,
      enhancement_model: row.enhancement_model || "",
      enhancement_error: row.enhancement_error || "",
    });
  }
  row.images = row.images
    .filter((image) => image && (image.original_image || image.enhanced_image))
    .map((image, index) => ({
      id: image.id || uid(),
      filename: image.filename || `product-${index + 1}.jpg`,
      original_image: image.original_image || image.enhanced_image,
      enhanced_image: image.enhanced_image || image.original_image,
      use_enhanced: image.use_enhanced !== false,
      enhancement_model: image.enhancement_model || "",
      enhancement_error: image.enhancement_error || "",
    }));
  return row.images;
}

function selectedProductImage(image) {
  if (!image) return "";
  return image.use_enhanced !== false ? image.enhanced_image || image.original_image : image.original_image;
}

function selectedImage(row) {
  return selectedProductImage(normalizeRowImages(row)[0]);
}

function selectedProductImages(row) {
  return normalizeRowImages(row)
    .map((image, index) => ({
      image_data_url: selectedProductImage(image),
      filename: image.filename || `product-${index + 1}.jpg`,
    }))
    .filter((image) => image.image_data_url);
}

function imageThumb(src, alt, badges = [], isSelected = false, onOpen = null) {
  const wrapper = document.createElement("div");
  wrapper.className = `thumb-card${isSelected ? " selected" : ""}`;
  wrapper.tabIndex = 0;
  wrapper.role = "button";
  wrapper.title = "مشاهده عکس";
  const image = document.createElement("img");
  image.className = "thumb";
  image.src = src;
  image.alt = alt;
  wrapper.appendChild(image);
  const badgeWrap = document.createElement("div");
  badgeWrap.className = "thumb-badges";
  for (const badge of badges) {
    const item = document.createElement("span");
    item.className = "thumb-badge";
    item.textContent = badge;
    badgeWrap.appendChild(item);
  }
  wrapper.appendChild(badgeWrap);
  if (onOpen) {
    wrapper.addEventListener("click", onOpen);
    wrapper.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      onOpen();
    });
  }
  return wrapper;
}

function setPreviewMode(image, mode) {
  const sources = {
    selected: selectedProductImage(image),
    enhanced: image.enhanced_image || image.original_image,
    original: image.original_image || image.enhanced_image,
  };
  const src = sources[mode] || sources.selected;
  els.imagePreviewImg.src = src;
  els.previewSelectedBtn.classList.toggle("active", mode === "selected");
  els.previewEnhancedBtn.classList.toggle("active", mode === "enhanced");
  els.previewOriginalBtn.classList.toggle("active", mode === "original");
}

function openImagePreview(row, image, index) {
  const productName = row.name ? ` - ${row.name}` : "";
  els.imagePreviewTitle.textContent = `عکس محصول ${index + 1}${productName}`;
  els.imagePreviewMeta.textContent = image.enhancement_error
    ? `نام فایل: ${image.filename || "product.jpg"} | ${image.enhancement_error}`
    : `نام فایل: ${image.filename || "product.jpg"}${
        image.enhancement_model ? ` | مدل: ${image.enhancement_model}` : ""
      }`;
  els.previewSelectedBtn.onclick = () => setPreviewMode(image, "selected");
  els.previewEnhancedBtn.onclick = () => setPreviewMode(image, "enhanced");
  els.previewOriginalBtn.onclick = () => setPreviewMode(image, "original");
  els.previewEnhancedBtn.disabled = !image.enhanced_image;
  els.previewOriginalBtn.disabled = !image.original_image;
  setPreviewMode(image, "selected");
  els.imagePreviewDialog.showModal();
}

function renderImageEditor(row) {
  const wrapper = document.createElement("div");
  wrapper.className = "image-editor";
  const images = normalizeRowImages(row);
  const list = document.createElement("div");
  list.className = "thumb-list";

  images.forEach((image, index) => {
    const item = document.createElement("div");
    item.className = "image-item";
    const badges = index === 0 ? ["اصلی"] : [String(index + 1)];
    if (image.enhancement_error) {
      badges.push("خطا");
      item.title = image.enhancement_error;
    }
    const thumb = imageThumb(
      selectedProductImage(image),
      `product image ${index + 1}`,
      badges,
      index === 0,
      () => openImagePreview(row, image, index)
    );
    item.appendChild(thumb);

    const controls = document.createElement("div");
    controls.className = "image-controls";
    controls.appendChild(actionButton("کاور", () => {
      row.images.splice(index, 1);
      row.images.unshift(image);
      saveState();
      render();
    }, index === 0, "mini"));
    controls.appendChild(actionButton("↑", () => {
      if (index <= 0) return;
      [row.images[index - 1], row.images[index]] = [row.images[index], row.images[index - 1]];
      saveState();
      render();
    }, index === 0, "mini icon"));
    controls.appendChild(actionButton("↓", () => {
      if (index >= row.images.length - 1) return;
      [row.images[index + 1], row.images[index]] = [row.images[index], row.images[index + 1]];
      saveState();
      render();
    }, index === row.images.length - 1, "mini icon"));
    controls.appendChild(actionButton("×", () => {
      row.images.splice(index, 1);
      setRowStatusFromValidation(row);
      saveState();
      render();
    }, row.images.length <= 1, "mini danger icon"));
    const enhance = document.createElement("label");
    enhance.className = "image-toggle";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = image.use_enhanced !== false;
    checkbox.addEventListener("change", () => {
      image.use_enhanced = checkbox.checked;
      saveState();
      render();
    });
    enhance.append(checkbox, "AI");
    controls.appendChild(enhance);
    item.appendChild(controls);
    list.appendChild(item);
  });

  const addLabel = document.createElement("label");
  addLabel.className = "add-photo-button";
  addLabel.textContent = "+ عکس";
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.multiple = true;
  input.addEventListener("change", async () => {
    const files = Array.from(input.files || []);
    input.value = "";
    await addFilesToRow(row, files);
  });
  addLabel.appendChild(input);
  wrapper.append(list, addLabel);
  return wrapper;
}

function rowStatusMessages(row) {
  return [...new Set([...(row.general_errors || []), ...(row.warnings || [])].filter(Boolean))];
}

function createCell(content, className = "") {
  const td = document.createElement("td");
  if (className) td.className = className;
  const wrapper = document.createElement("div");
  wrapper.className = "cell-content";
  if (content instanceof Node) {
    wrapper.appendChild(content);
  } else {
    wrapper.innerHTML = content;
  }
  td.appendChild(wrapper);
  return td;
}

function fieldErrors(row, keys) {
  const errors = [];
  const source = row.field_errors || {};
  for (const key of keys.flat()) {
    if (Array.isArray(source[key])) errors.push(...source[key]);
  }
  return [...new Set(errors)];
}

function appendCellErrors(wrapper, row, ...keys) {
  const errors = fieldErrors(row, keys);
  for (const error of errors) {
    const note = document.createElement("span");
    note.className = "cell-error";
    note.textContent = error;
    wrapper.appendChild(note);
  }
  if (errors.length) wrapper.classList.add("has-error");
  return wrapper;
}

function validatedCell(content, row, ...keys) {
  const wrapper = document.createElement("div");
  wrapper.className = "cell-stack";
  if (content instanceof Node) wrapper.appendChild(content);
  else wrapper.innerHTML = content;
  appendCellErrors(wrapper, row, ...keys);
  return createCell(wrapper);
}

function bindInput(input, row, key, transform = (value) => value) {
  input.addEventListener("change", () => {
    row[key] = transform(input.type === "checkbox" ? input.checked : input.value);
    setRowStatusFromValidation(row);
    saveState();
    render();
  });
  return input;
}

function bindVariantInput(input, row, variantIndex, key, transform = (value) => value) {
  input.addEventListener("change", () => {
    row.variants = Array.isArray(row.variants) ? row.variants : [];
    row.variants[variantIndex] = row.variants[variantIndex] || {};
    row.variants[variantIndex][key] = transform(input.value);
    setRowStatusFromValidation(row);
    saveState();
    render();
  });
  return input;
}

function bindVariantPropertyInput(input, row, variantIndex, propertyIndex, key) {
  input.addEventListener("change", () => {
    row.variants = Array.isArray(row.variants) ? row.variants : [];
    row.variants[variantIndex] = row.variants[variantIndex] || {};
    const variant = row.variants[variantIndex];
    variant.properties = Array.isArray(variant.properties) ? variant.properties : [];
    variant.properties[propertyIndex] = variant.properties[propertyIndex] || {};
    variant.properties[propertyIndex][key] = input.value;
    setRowStatusFromValidation(row);
    saveState();
    render();
  });
  return input;
}

function field(labelText, control, noteText = "", row = null, errorKeys = []) {
  const wrapper = document.createElement("label");
  wrapper.className = "field-stack";
  const label = document.createElement("span");
  label.textContent = labelText;
  wrapper.appendChild(label);
  wrapper.appendChild(control);
  if (noteText) {
    const note = document.createElement("small");
    note.textContent = noteText;
    wrapper.appendChild(note);
  }
  if (row && errorKeys.length) appendCellErrors(wrapper, row, errorKeys);
  return wrapper;
}

function textInput(row, key, extra = {}) {
  const input = document.createElement("input");
  input.type = extra.type || "text";
  input.value = row[key] ?? "";
  input.placeholder = extra.placeholder || "";
  if (extra.list) input.setAttribute("list", extra.list);
  return bindInput(input, row, key, extra.transform || ((value) => value));
}

function rawInput(value = "", extra = {}) {
  const input = document.createElement("input");
  input.type = extra.type || "text";
  input.value = value ?? "";
  input.placeholder = extra.placeholder || "";
  return input;
}

function selectInput(row, key, options) {
  const select = document.createElement("select");
  select.className = "unit-select";
  const currentValue = row[key] ?? "";
  for (const option of options) {
    const element = document.createElement("option");
    element.value = option.id;
    element.textContent = option.title;
    if (String(option.id) === String(currentValue)) element.selected = true;
    select.appendChild(element);
  }
  return bindInput(select, row, key);
}

function editableTextCell(row, key, placeholder = "") {
  const editor = document.createElement("div");
  editor.className = "editable-cell";
  editor.setAttribute("contenteditable", "plaintext-only");
  editor.tabIndex = 0;
  editor.role = "textbox";
  editor.setAttribute("aria-multiline", "true");
  editor.dataset.placeholder = placeholder;
  editor.textContent = row[key] ?? "";
  let originalValue = editor.textContent;

  const commit = () => {
    const nextValue = editor.textContent.trim();
    if (row[key] === nextValue) return;
    row[key] = nextValue;
    originalValue = nextValue;
    setRowStatusFromValidation(row);
    saveState();
  };

  editor.addEventListener("focus", () => {
    originalValue = editor.textContent;
  });
  editor.addEventListener("blur", commit);
  editor.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      editor.textContent = originalValue;
      editor.blur();
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      editor.blur();
    }
  });
  editor.addEventListener("paste", (event) => {
    event.preventDefault();
    const text = event.clipboardData?.getData("text/plain") || "";
    document.execCommand("insertText", false, text);
  });
  return editor;
}

function renderHeader() {
  const dynamic = dynamicAttributeIds();
  const tr = document.createElement("tr");
  for (const title of FIXED_HEADERS) {
    const th = document.createElement("th");
    th.textContent = title;
    if (title === "عملیات") th.className = "sticky-col";
    tr.appendChild(th);
  }
    for (const attr of dynamic) {
      const th = document.createElement("th");
      th.textContent = attr.unit ? `${attr.title} (${attr.unit})` : attr.title;
    if (isRequiredAttribute(attr)) th.textContent += " *";
    tr.appendChild(th);
  }
  els.tableHead.replaceChildren(tr);
}

function renderRows() {
  const dynamic = dynamicAttributeIds();
  const fragment = document.createDocumentFragment();
  if (!state.rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = FIXED_HEADERS.length + dynamic.length;
    td.className = "muted";
    td.textContent = "برای شروع، عکس محصول را اضافه کنید.";
    tr.appendChild(td);
    fragment.appendChild(tr);
    els.tableBody.replaceChildren(fragment);
    return;
  }

  for (const row of state.rows) {
    const tr = document.createElement("tr");
    tr.dataset.rowId = row.id;

    const rowControls = document.createElement("div");
    rowControls.className = "row-control-actions";
    rowControls.appendChild(
      actionButton(
        row.product_id ? "ویرایش" : "ثبت",
        () => openSubmitDialog(row.id),
        row.status !== "Ready" && row.status !== "Submitted",
        "mini primary"
      )
    );
    rowControls.appendChild(actionButton("حذف", () => deleteRow(row.id), false, "mini danger"));
    tr.appendChild(createCell(rowControls, "sticky-col row-control-cell"));

    const imageCell = validatedCell(renderImageEditor(row), row, "image");
    imageCell.classList.add("image-cell");
    tr.appendChild(imageCell);

    const statusWrap = document.createElement("div");
    statusWrap.className = "row-status";
    statusWrap.innerHTML = `<span class="status-pill ${statusClass(row.status)}">${statusLabel(row.status)}</span>`;
    const actions = document.createElement("div");
    actions.className = "row-actions";
    actions.appendChild(
      actionButton(
        analyzeButtonText(row),
        () => analyzeRow(row.id),
        row.status === "Analyzing",
        analyzeButtonClass(row)
      )
    );
    statusWrap.appendChild(actions);
    for (const message of rowStatusMessages(row)) {
      const note = document.createElement("span");
      note.className = "status-message warning-text";
      note.textContent = message;
      statusWrap.appendChild(note);
    }
    const statusCell = createCell(statusWrap);
    statusCell.classList.add("status-cell");
    tr.appendChild(statusCell);

    const categoryWrap = document.createElement("div");
    const categoryInput = document.createElement("input");
    categoryInput.setAttribute("list", "categoryOptions");
    categoryInput.value = row.category_id ? `${row.category_id} - ${row.category_title || ""}` : "";
    categoryInput.addEventListener("change", async () => {
      const category = parseCategoryInput(categoryInput.value);
      if (!category) return;
      row.category_id = category.id;
      row.category_title = category.title;
      row.category_confidence = row.category_confidence || 1;
      applyCategoryUnit(row, category);
      applyEstimatedPackageWeight(row, {});
      applySaleUnit(row, {});
      await ensureAttributes(category.id);
      setRowStatusFromValidation(row);
      saveState();
      render();
    });
    categoryWrap.appendChild(categoryInput);
    const confidence = document.createElement("span");
    confidence.className = "cell-note";
    confidence.textContent = row.category_confidence ? `دقت پیشنهاد: ${Math.round(row.category_confidence * 100)}٪` : "";
    categoryWrap.appendChild(confidence);
    tr.appendChild(validatedCell(categoryWrap, row, "category"));

    tr.appendChild(validatedCell(textInput(row, "name"), row, "name"));
    tr.appendChild(createCell(editableTextCell(row, "brief", "معرفی کوتاه")));
    tr.appendChild(createCell(editableTextCell(row, "description", "توضیحات محصول")));
    const priceWrap = document.createElement("div");
    priceWrap.className = "price-cell";
    priceWrap.appendChild(textInput(row, "price_final", { type: "number", placeholder: "قیمت فروش" }));
    const note = document.createElement("span");
    note.className = "cell-note";
    note.textContent = row.price_suggested
      ? `پیشنهادی: ${formatPrice(row.price_suggested)} | نمونه: ${
          row.price_sample_count || 0
        } | ${row.price_confidence || ""}${priceCriteriaLabel(row)}`
      : "قیمت پیشنهادی ثبت نشده";
    priceWrap.appendChild(note);
    priceWrap.appendChild(renderPriceSamples(row));
    const priceCell = validatedCell(priceWrap, row, "price");
    priceCell.classList.add("price-table-cell");
    tr.appendChild(priceCell);

    tr.appendChild(validatedCell(textInput(row, "stock", { type: "number" }), row, "stock"));

    const weightWrap = document.createElement("div");
    weightWrap.className = "compact-fields pair-fields";
    weightWrap.appendChild(
      field("وزن خالص", textInput(row, "weight", { type: "number", placeholder: "500" }), "گرم")
    );
    weightWrap.appendChild(
      field(
        "با بسته‌بندی",
        textInput(row, "package_weight", { type: "number", placeholder: "650" }),
        "بیشتر از وزن خالص",
        row,
        ["package_weight"]
      )
    );
    tr.appendChild(createCell(weightWrap));

    const unitWrap = document.createElement("div");
    unitWrap.className = "compact-fields pair-fields";
    const unitOptions = unitTypeOptionsForRow(row);
    unitWrap.appendChild(
      field(
        "مقدار فروش",
        textInput(row, "unit_quantity", { type: "number", placeholder: "1 یا 500" }),
        "",
        row,
        ["unit"]
      )
    );
    unitWrap.appendChild(field("واحد فروش", selectInput(row, "unit_type", unitOptions), "", row, ["unit"]));
    tr.appendChild(createCell(unitWrap));

    const shippingWrap = document.createElement("div");
    shippingWrap.className = "compact-fields";
    shippingWrap.appendChild(field("زمان آماده‌سازی", textInput(row, "preparation_days", { type: "number" }), "روز"));
    tr.appendChild(createCell(shippingWrap));

    const variantsCell = validatedCell(renderVariantsEditor(row), row, "variants");
    variantsCell.classList.add("variants-cell");
    tr.appendChild(variantsCell);

    tr.appendChild(createCell(row.product_id ? String(row.product_id) : "<span class='muted'>-</span>"));

    for (const attr of dynamic) {
      const input = document.createElement("input");
      input.value = row.attributes?.[attr.id] || "";
      input.placeholder = isRequiredAttribute(attr) ? "لازم است" : "";
      input.addEventListener("change", () => {
        row.attributes = row.attributes || {};
        row.attributes[attr.id] = input.value;
        setRowStatusFromValidation(row);
        saveState();
        render();
      });
      tr.appendChild(validatedCell(input, row, `attribute:${attr.id}`));
    }

    fragment.appendChild(tr);
  }
  els.tableBody.replaceChildren(fragment);
}

function unitTypeOptionsForRow(row) {
  const category = categoryById(row.category_id);
  const suggestedUnitType = unitTypeFromCategory(category);
  const options = [...UNIT_TYPES];
  if (suggestedUnitType) {
    const option = options.find((item) => String(item.id) === String(suggestedUnitType));
    if (option && !option.title.includes("پیشنهادی")) {
      option.title = `${option.title} (پیشنهادی)`;
    }
  }
  return options;
}

function normalizedVariants(row) {
  const variants = Array.isArray(row.variants) ? row.variants : [];
  return variants
    .map((variant) => {
      const properties = Array.isArray(variant.properties) ? variant.properties : [];
      return {
        primary_price: numberOrNull(variant.primary_price),
        stock: numberOrNull(variant.stock),
        properties: properties
          .map((property) => ({
            property: String(property.property || "").trim(),
            value: String(property.value || "").trim(),
          }))
          .filter((property) => property.property || property.value),
      };
    })
    .filter((variant) => variant.primary_price !== null || variant.stock !== null || variant.properties.length);
}

function renderVariantsEditor(row) {
  row.variants = Array.isArray(row.variants) ? row.variants : [];
  const wrapper = document.createElement("div");
  wrapper.className = "variants-editor";

  if (!row.variants.length) {
    const empty = document.createElement("span");
    empty.className = "cell-note";
    empty.textContent = "بدون تنوع";
    wrapper.appendChild(empty);
  }

  row.variants.forEach((variant, variantIndex) => {
    variant.properties = Array.isArray(variant.properties) && variant.properties.length ? variant.properties : [{ property: "", value: "" }];
    const panel = document.createElement("div");
    panel.className = "variant-panel";

    const title = document.createElement("div");
    title.className = "variant-title";
    title.append(`تنوع ${variantIndex + 1}`);
    const remove = actionButton("حذف", () => {
      row.variants.splice(variantIndex, 1);
      setRowStatusFromValidation(row);
      saveState();
      render();
    });
    remove.className = "mini danger";
    title.appendChild(remove);
    panel.appendChild(title);

    const baseGrid = document.createElement("div");
    baseGrid.className = "variant-grid";
    baseGrid.appendChild(field("قیمت", bindVariantInput(rawInput(variant.primary_price, { type: "number" }), row, variantIndex, "primary_price")));
    baseGrid.appendChild(field("موجودی", bindVariantInput(rawInput(variant.stock, { type: "number" }), row, variantIndex, "stock")));
    panel.appendChild(baseGrid);

    variant.properties.forEach((property, propertyIndex) => {
      const propGrid = document.createElement("div");
      propGrid.className = "variant-prop-grid";
      propGrid.appendChild(
        field(
          "ویژگی",
          bindVariantPropertyInput(rawInput(property.property, { placeholder: "رنگ" }), row, variantIndex, propertyIndex, "property")
        )
      );
      propGrid.appendChild(
        field(
          "مقدار",
          bindVariantPropertyInput(rawInput(property.value, { placeholder: "قرمز" }), row, variantIndex, propertyIndex, "value")
        )
      );
      const removeProperty = actionButton("×", () => {
        variant.properties.splice(propertyIndex, 1);
        if (!variant.properties.length) variant.properties.push({ property: "", value: "" });
        setRowStatusFromValidation(row);
        saveState();
        render();
      });
      removeProperty.className = "mini";
      propGrid.appendChild(removeProperty);
      panel.appendChild(propGrid);
    });

    const addProperty = actionButton("+ ویژگی", () => {
      variant.properties.push({ property: "", value: "" });
      saveState();
      render();
    });
    addProperty.className = "mini";
    panel.appendChild(addProperty);
    wrapper.appendChild(panel);
  });

    const addVariant = actionButton("+ تنوع", () => {
    row.variants.push({
      primary_price: row.price_final || "",
      stock: row.stock || "",
      properties: [{ property: "", value: "" }],
    });
    setRowStatusFromValidation(row);
    saveState();
    render();
  });
  addVariant.className = "mini primary";
  wrapper.appendChild(addVariant);

  return wrapper;
}

function renderPriceSamples(row) {
  const samples = Array.isArray(row.price_samples) ? row.price_samples : [];
  const details = document.createElement("details");
  details.className = "price-samples";
  const summary = document.createElement("summary");
  summary.textContent = samples.length ? `${samples.length} محصول مشابه` : "نمونه‌های قیمت";
  details.appendChild(summary);

  if (!samples.length) {
    const empty = document.createElement("span");
    empty.className = "cell-note";
    empty.textContent = "بعد از تحلیل، محصولات مشابه اینجا نمایش داده می‌شوند.";
    details.appendChild(empty);
    return details;
  }

  const list = document.createElement("ol");
  for (const sample of samples) {
    const item = document.createElement("li");
    const title = sample.name || sample.title || `محصول ${sample.id || ""}`.trim() || "محصول مشابه";
    const price = formatPrice(sample.price);
    const main = document.createElement(sample.url ? "a" : "span");
    main.textContent = title;
    if (sample.url) {
      main.href = sample.url;
      main.target = "_blank";
      main.rel = "noopener noreferrer";
    }
    const meta = document.createElement("span");
    meta.className = "price-sample-meta";
    const comparablePrice =
      sample.comparable_price && Number(sample.comparable_price) !== Number(sample.price)
        ? `قیمت متناسب با وزن: ${formatPrice(sample.comparable_price)}`
        : "";
    const sampleWeight = sample.detected_weight_grams
      ? `وزن محصول: ${Number(sample.detected_weight_grams).toLocaleString("fa-IR")} گرم`
      : "";
    const weightRatio =
      sample.weight_ratio && Number(sample.weight_ratio) !== 1
        ? `نسبت وزن: ${Number(sample.weight_ratio).toLocaleString("fa-IR")}`
        : "";
    const typeScore =
      sample.type_score !== undefined ? `شباهت نوع: ${Math.round(Number(sample.type_score) * 100)}٪` : "";
    const detailsText = [
      price,
      comparablePrice,
      sampleWeight,
      weightRatio,
      typeScore,
      sample.vendor_title ? `غرفه: ${sample.vendor_title}` : "",
      sample.category_title ? `دسته‌بندی: ${sample.category_title}` : "",
      sample.id ? `ID: ${sample.id}` : "",
    ].filter(Boolean);
    meta.textContent = detailsText.join(" | ");
    item.append(main, meta);
    list.appendChild(item);
  }
  details.appendChild(list);
  return details;
}

function priceCriteriaLabel(row) {
  const criteria = row.price_criteria || {};
  const parts = [];
  if (criteria.target_weight_grams) {
    parts.push(`وزن: ${Number(criteria.target_weight_grams).toLocaleString("fa-IR")} گرم`);
  }
  if (criteria.price_basis === "used_price") {
    parts.push("قیمت متناسب با وزن");
  }
  if (criteria.sample_selection === "close_weight") {
    parts.push("نمونه‌های وزن نزدیک");
  } else if (criteria.sample_selection === "usable_weight") {
    parts.push("نمونه‌های وزن قابل‌مقایسه");
  } else if (criteria.sample_selection === "broad_weight") {
    parts.push("نمونه‌های وزن دورتر");
  }
  return parts.length ? ` | ${parts.join(" | ")}` : "";
}

function priceQueryForRow(row) {
  return [row.name, row.category_title].filter(Boolean).join(" ");
}

function actionButton(label, onClick, disabled = false, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.disabled = disabled;
  if (className) button.className = className;
  button.addEventListener("click", onClick);
  return button;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function rowById(rowId) {
  return state.rows.find((row) => row.id === rowId);
}

function activeMobileRow() {
  return rowById(mobileState.activeRowId);
}

function clampMobileStep(step) {
  const numeric = Number(step);
  if (!Number.isFinite(numeric)) return 0;
  return Math.min(Math.max(Math.round(numeric), 0), MOBILE_STEPS.length - 1);
}

function mobileRowTitle(row, index = 0) {
  return row?.name || row?.filename || `محصول ${index + 1}`;
}

function mobileRowMessages(row, limit = 2) {
  const messages = [...(row?.general_errors || []), ...(row?.errors || []), ...(row?.warnings || [])].filter(Boolean);
  return [...new Set(messages)].slice(0, limit);
}

function setActiveMobileRow(rowId, step = 0) {
  mobileState.activeRowId = rowId;
  mobileState.step = clampMobileStep(step);
  render();
}

async function setMobileStep(step) {
  const row = activeMobileRow();
  const nextStep = clampMobileStep(step);
  if (row?.category_id && nextStep >= 2) {
    try {
      await ensureAttributes(row.category_id);
    } catch (error) {
      addRowWarning(row, error.message);
    }
  }
  if (row && nextStep === MOBILE_STEPS.length - 1) {
    setRowStatusFromValidation(row);
    saveState();
  }
  mobileState.step = nextStep;
  render();
}

function mobileTextArea(row, key, placeholder = "") {
  const textarea = document.createElement("textarea");
  textarea.className = "mobile-textarea";
  textarea.value = row[key] ?? "";
  textarea.placeholder = placeholder;
  textarea.rows = key === "description" ? 5 : 3;
  textarea.addEventListener("change", () => {
    row[key] = textarea.value.trim();
    setRowStatusFromValidation(row);
    saveState();
    render();
  });
  return textarea;
}

function mobileSection(title, ...children) {
  const section = document.createElement("section");
  section.className = "mobile-card-section";
  if (title) {
    const heading = document.createElement("h3");
    heading.textContent = title;
    section.appendChild(heading);
  }
  section.append(...children.filter(Boolean));
  return section;
}

function mobileSubsection(title, child) {
  const wrapper = document.createElement("div");
  wrapper.className = "mobile-subsection";
  const heading = document.createElement("h4");
  heading.textContent = title;
  wrapper.append(heading, child);
  return wrapper;
}

function mobileInlineFields(...children) {
  const wrapper = document.createElement("div");
  wrapper.className = "mobile-inline-fields";
  wrapper.append(...children.filter(Boolean));
  return wrapper;
}

function mobileMessageList(messages, className = "") {
  const list = document.createElement("div");
  list.className = `mobile-message-list${className ? ` ${className}` : ""}`;
  if (!messages.length) {
    const empty = document.createElement("span");
    empty.className = "cell-note";
    empty.textContent = "موردی برای نمایش نیست.";
    list.appendChild(empty);
    return list;
  }
  for (const message of [...new Set(messages.filter(Boolean))]) {
    const item = document.createElement("span");
    item.textContent = message;
    list.appendChild(item);
  }
  return list;
}

function renderMobileCategoryField(row) {
  const categoryInput = document.createElement("input");
  categoryInput.setAttribute("list", "categoryOptions");
  categoryInput.value = row.category_id ? `${row.category_id} - ${row.category_title || ""}` : "";
  categoryInput.placeholder = "جستجو و انتخاب دسته‌بندی";
  categoryInput.addEventListener("focus", () => {
    loadCategories(false).catch((error) => setStatus(error.message));
  });
  categoryInput.addEventListener("change", async () => {
    const category = parseCategoryInput(categoryInput.value);
    if (!category) {
      setStatus("دسته‌بندی معتبر را از لیست انتخاب کنید");
      return;
    }
    row.category_id = category.id;
    row.category_title = category.title;
    row.category_confidence = row.category_confidence || 1;
    applyCategoryUnit(row, category);
    applyEstimatedPackageWeight(row, {});
    applySaleUnit(row, {});
    try {
      await ensureAttributes(category.id);
    } catch (error) {
      addRowWarning(row, error.message);
    }
    setRowStatusFromValidation(row);
    saveState();
    render();
  });
  const confidence = row.category_confidence ? `دقت پیشنهاد: ${Math.round(row.category_confidence * 100)}٪` : "";
  return field("دسته‌بندی", categoryInput, confidence, row, ["category"]);
}

function renderMobileAttributes(row) {
  const wrapper = document.createElement("div");
  wrapper.className = "mobile-attribute-list";
  if (!row.category_id) {
    const note = document.createElement("p");
    note.className = "cell-note";
    note.textContent = "بعد از انتخاب دسته‌بندی، ویژگی‌های لازم اینجا نمایش داده می‌شود.";
    wrapper.appendChild(note);
    return wrapper;
  }

  const attrs = requiredAttributesForCategory(row.category_id);
  if (!attrs.length) {
    const note = document.createElement("p");
    note.className = "cell-note";
    note.textContent = "برای این دسته ویژگی اجباری ثبت نشده است.";
    wrapper.appendChild(note);
    return wrapper;
  }

  for (const attr of attrs) {
    const input = document.createElement("input");
    input.value = row.attributes?.[attr.id] || "";
    input.placeholder = attr.unit ? `${attr.title} (${attr.unit})` : attr.title;
    input.addEventListener("change", () => {
      row.attributes = row.attributes || {};
      row.attributes[attr.id] = input.value.trim();
      setRowStatusFromValidation(row);
      saveState();
      render();
    });
    wrapper.appendChild(field(`${attr.title} *`, input, attr.unit || "", row, [`attribute:${attr.id}`]));
  }
  return wrapper;
}

function renderMobileQueue() {
  if (!els.mobileQueue) return;
  const fragment = document.createDocumentFragment();
  const header = document.createElement("header");
  header.className = "mobile-queue-header";
  const headingWrap = document.createElement("div");
  const title = document.createElement("h2");
  title.textContent = "صف محصولات";
  const meta = document.createElement("p");
  const readyCount = state.rows.filter((row) => row.status === "Ready" || row.status === "Submitted").length;
  meta.textContent = state.rows.length
    ? `${state.rows.length.toLocaleString("fa-IR")} محصول، ${readyCount.toLocaleString("fa-IR")} آماده`
    : "برای شروع، عکس محصول را اضافه کنید.";
  headingWrap.append(title, meta);
  const addLabel = document.createElement("label");
  addLabel.className = "mobile-add-photo";
  addLabel.htmlFor = "imageInput";
  addLabel.textContent = "افزودن عکس";
  header.append(headingWrap, addLabel);
  fragment.appendChild(header);

  if (!state.rows.length) {
    const empty = document.createElement("div");
    empty.className = "mobile-empty-state";
    empty.innerHTML = "<h3>عکس‌های محصول را انتخاب کنید</h3><p>هر عکس از ورودی اصلی، یک محصول جدا در این صف می‌سازد.</p>";
    fragment.appendChild(empty);
    els.mobileQueue.replaceChildren(fragment);
    return;
  }

  const list = document.createElement("div");
  list.className = "mobile-product-list";
  state.rows.forEach((row, index) => {
    const card = document.createElement("article");
    card.className = `mobile-product-card${row.id === mobileState.activeRowId ? " active" : ""}`;
    card.tabIndex = 0;
    card.dataset.rowId = row.id;
    card.addEventListener("click", (event) => {
      if (event.target.closest("button,label,input")) return;
      setActiveMobileRow(row.id, mobileState.step);
    });
    card.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      setActiveMobileRow(row.id, mobileState.step);
    });

    const image = selectedImage(row);
    if (image) {
      const thumb = document.createElement("img");
      thumb.className = "mobile-product-thumb";
      thumb.src = image;
      thumb.alt = mobileRowTitle(row, index);
      card.appendChild(thumb);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "mobile-thumb-placeholder";
      placeholder.textContent = String(index + 1).toLocaleString("fa-IR");
      card.appendChild(placeholder);
    }

    const body = document.createElement("div");
    body.className = "mobile-product-body";
    const cardTitle = document.createElement("h3");
    cardTitle.textContent = mobileRowTitle(row, index);
    const status = document.createElement("span");
    status.className = `status-pill ${statusClass(row.status)}`;
    status.textContent = statusLabel(row.status);
    body.append(cardTitle, status);
    for (const message of mobileRowMessages(row, 1)) {
      const note = document.createElement("p");
      note.className = "mobile-card-warning";
      note.textContent = message;
      body.appendChild(note);
    }
    card.appendChild(body);

    const actions = document.createElement("div");
    actions.className = "mobile-card-actions";
    actions.appendChild(actionButton("ادامه", () => setActiveMobileRow(row.id, mobileState.step), false, "mini primary"));
    actions.appendChild(actionButton("حذف", () => deleteRow(row.id), false, "mini danger"));
    card.appendChild(actions);
    list.appendChild(card);
  });
  fragment.appendChild(list);
  els.mobileQueue.replaceChildren(fragment);
}

function renderMobileStepNav() {
  const nav = document.createElement("nav");
  nav.className = "mobile-stepper";
  nav.setAttribute("aria-label", "مراحل تکمیل محصول");
  MOBILE_STEPS.forEach((step, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `mobile-step-pill${index === mobileState.step ? " active" : ""}`;
    button.textContent = `${String(index + 1).toLocaleString("fa-IR")} ${step.title}`;
    button.addEventListener("click", () => {
      setMobileStep(index).catch((error) => setStatus(error.message));
    });
    nav.appendChild(button);
  });
  return nav;
}

function renderMobileMediaStep(row) {
  const statusWrap = document.createElement("div");
  statusWrap.className = "mobile-status-row";
  const status = document.createElement("span");
  status.className = `status-pill ${statusClass(row.status)}`;
  status.textContent = statusLabel(row.status);
  const analyze = actionButton(analyzeButtonText(row), () => analyzeRow(row.id), row.status === "Analyzing", analyzeButtonClass(row));
  statusWrap.append(status, analyze);

  return mobileSection(
    "عکس و تحلیل",
    statusWrap,
    renderImageEditor(row),
    mobileMessageList(mobileRowMessages(row, 4), "compact")
  );
}

function renderMobileBasicsStep(row) {
  const priceWrap = document.createElement("div");
  priceWrap.className = "mobile-price-control";
  priceWrap.appendChild(field("قیمت فروش", textInput(row, "price_final", { type: "number", placeholder: "قیمت به تومان" }), "", row, ["price"]));
  const priceNote = document.createElement("p");
  priceNote.className = "cell-note";
  priceNote.textContent = row.price_suggested
    ? `پیشنهادی: ${formatPrice(row.price_suggested)} | نمونه: ${row.price_sample_count || 0}`
    : "بعد از تحلیل یا ورود نام، قیمت پیشنهادی قابل دریافت است.";
  const priceButton = actionButton("پیشنهاد قیمت", () => suggestPrice(row.id), !row.name, "mini");
  priceWrap.append(priceNote, priceButton);

  return mobileSection(
    "اطلاعات اصلی",
    renderMobileCategoryField(row),
    field("نام محصول", textInput(row, "name", { placeholder: "نام قابل نمایش در غرفه" }), "", row, ["name"]),
    priceWrap,
    mobileInlineFields(
      field("موجودی", textInput(row, "stock", { type: "number", placeholder: "1" }), "", row, ["stock"]),
      field("زمان آماده‌سازی", textInput(row, "preparation_days", { type: "number", placeholder: "3" }), "روز")
    )
  );
}

function renderMobileDetailsStep(row) {
  const unitOptions = unitTypeOptionsForRow(row);
  const variantsDetails = document.createElement("details");
  variantsDetails.className = "mobile-collapse";
  const variantsSummary = document.createElement("summary");
  variantsSummary.textContent = "تنوع‌ها";
  variantsDetails.append(variantsSummary, renderVariantsEditor(row));

  return mobileSection(
    "جزئیات تکمیلی",
    field("معرفی کوتاه", mobileTextArea(row, "brief", "متن کوتاه برای معرفی محصول")),
    field("توضیحات", mobileTextArea(row, "description", "توضیحات کامل محصول")),
    mobileInlineFields(
      field("وزن خالص", textInput(row, "weight", { type: "number", placeholder: "500" }), "گرم"),
      field(
        "وزن با بسته‌بندی",
        textInput(row, "package_weight", { type: "number", placeholder: "650" }),
        "بیشتر از وزن خالص",
        row,
        ["package_weight"]
      )
    ),
    mobileInlineFields(
      field("مقدار فروش", textInput(row, "unit_quantity", { type: "number", placeholder: "1 یا 500" }), "", row, ["unit"]),
      field("واحد فروش", selectInput(row, "unit_type", unitOptions), "", row, ["unit"])
    ),
    mobileSubsection("ویژگی‌های اجباری", renderMobileAttributes(row)),
    variantsDetails
  );
}

function renderMobileReviewStep(row) {
  const reviewErrors = validateRow(row);
  const wrapper = document.createElement("div");
  wrapper.className = "mobile-review";
  const messages = [...new Set([...reviewErrors, ...(row.general_errors || [])].filter(Boolean))];
  if (messages.length) {
    const title = document.createElement("h3");
    title.textContent = "موارد لازم برای ثبت";
    wrapper.append(title, mobileMessageList(messages, "errors"));
  } else {
    const ready = document.createElement("div");
    ready.className = "mobile-ready-box";
    ready.textContent = row.product_id ? "این محصول آماده ویرایش است." : "این محصول آماده ثبت در غرفه است.";
    wrapper.appendChild(ready);
  }

  const summary = document.createElement("dl");
  summary.className = "mobile-review-grid";
  const items = [
    ["نام", row.name || "-"],
    ["دسته‌بندی", row.category_title || "-"],
    ["قیمت", row.price_final ? formatPrice(row.price_final) : "-"],
    ["موجودی", row.stock || "-"],
    ["زمان آماده‌سازی", row.preparation_days ? `${row.preparation_days} روز` : "-"],
    ["عکس‌ها", `${selectedProductImages(row).length.toLocaleString("fa-IR")} عکس`],
  ];
  if (row.product_id) items.push(["شناسه", row.product_id]);
  for (const [label, value] of items) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    summary.append(dt, dd);
  }
  wrapper.appendChild(summary);

  const details = document.createElement("details");
  details.className = "mobile-technical-details";
  const summaryTitle = document.createElement("summary");
  summaryTitle.textContent = "جزئیات فنی";
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(buildSubmissionPreview(row), null, 2);
  details.append(summaryTitle, pre);
  wrapper.appendChild(details);
  return mobileSection("بازبینی و ثبت", wrapper);
}

function renderMobileBottomBar(row) {
  const footer = document.createElement("footer");
  footer.className = "mobile-bottom-bar";
  const previous = actionButton(
    "قبلی",
    () => setMobileStep(mobileState.step - 1).catch((error) => setStatus(error.message)),
    mobileState.step === 0
  );
  footer.appendChild(previous);
  if (mobileState.step < MOBILE_STEPS.length - 1) {
    footer.appendChild(
      actionButton("بعدی", () => setMobileStep(mobileState.step + 1).catch((error) => setStatus(error.message)), false, "primary")
    );
    return footer;
  }

  const errors = validateRow(row);
  footer.appendChild(
    actionButton(
      row.product_id ? "ویرایش محصول" : "ثبت محصول",
      () => submitMobileRow(row.id),
      Boolean(errors.length || row.status === "Submitting"),
      "primary"
    )
  );
  return footer;
}

function renderMobileWizard() {
  if (!els.mobileWizard) return;
  const row = activeMobileRow();
  if (!row) {
    els.mobileWizard.hidden = true;
    els.mobileWizard.replaceChildren();
    return;
  }

  const index = state.rows.findIndex((item) => item.id === row.id);
  const header = document.createElement("header");
  header.className = "mobile-wizard-header";
  const titleWrap = document.createElement("div");
  const title = document.createElement("h2");
  title.textContent = mobileRowTitle(row, index);
  const meta = document.createElement("p");
  meta.textContent = `محصول ${(index + 1).toLocaleString("fa-IR")} از ${state.rows.length.toLocaleString("fa-IR")}`;
  titleWrap.append(title, meta);
  const status = document.createElement("span");
  status.className = `status-pill ${statusClass(row.status)}`;
  status.textContent = statusLabel(row.status);
  header.append(titleWrap, status);

  const stepId = MOBILE_STEPS[mobileState.step]?.id || MOBILE_STEPS[0].id;
  let content = null;
  if (stepId === "media") content = renderMobileMediaStep(row);
  if (stepId === "basics") content = renderMobileBasicsStep(row);
  if (stepId === "details") content = renderMobileDetailsStep(row);
  if (stepId === "review") content = renderMobileReviewStep(row);

  els.mobileWizard.hidden = false;
  els.mobileWizard.replaceChildren(header, renderMobileStepNav(), renderMobileBottomBar(row), content);
}

function renderMobileWorkflow() {
  if (!els.mobileWorkflow) return;
  if (!state.rows.length) {
    mobileState.activeRowId = "";
    mobileState.step = 0;
  } else if (!activeMobileRow()) {
    mobileState.activeRowId = state.rows[0].id;
    mobileState.step = 0;
  }
  mobileState.step = clampMobileStep(mobileState.step);
  renderMobileQueue();
  renderMobileWizard();
}

async function submitMobileRow(rowId) {
  const row = rowById(rowId);
  if (!row) return;
  setRowStatusFromValidation(row);
  if (row.errors.length) {
    row.status = "Needs Review";
    saveState();
    render();
    setStatus("موارد مشخص‌شده را کامل کنید و دوباره ثبت کنید");
    return;
  }
  await submitRow(rowId);
}

function render() {
  updateCategoryOptions();
  renderHeader();
  renderRows();
  renderMobileWorkflow();
}

async function loadCategories(force = false) {
  if (state.categories.length && !force) return;
  setStatus("در حال به‌روزرسانی دسته‌ها...");
  const query = state.settings.basalamToken ? `?token=${encodeURIComponent(state.settings.basalamToken)}` : "";
  const payload = await apiFetch(`/api/basalam/categories${query}`);
  state.categories = Array.isArray(payload.flat) ? payload.flat : [];
  state.categorySchemaVersion = CATEGORY_SCHEMA_VERSION;
  applyCategoryUnitsToRows();
  saveState();
  render();
  setStatus("دسته‌ها به‌روز شد");
}

async function ensureAttributes(categoryId) {
  if (!categoryId || state.attributesByCategory[String(categoryId)]) return;
  const params = new URLSearchParams();
  if (state.settings.basalamToken) params.set("token", state.settings.basalamToken);
  if (state.settings.vendorId) params.set("vendor_id", state.settings.vendorId);
  const payload = await apiFetch(`/api/basalam/categories/${categoryId}/attributes?${params.toString()}`);
  state.attributesByCategory[String(categoryId)] = payload;
  saveState();
}

async function verifyToken() {
  syncSettingsFromForm();
  if (!state.settings.basalamToken) {
    setStatus("توکن دسترسی باسلام را وارد کنید");
    return;
  }
  setStatus("در حال شناسایی غرفه...");
  const payload = await apiFetch("/api/basalam/me", {
    method: "POST",
    body: JSON.stringify({ token: state.settings.basalamToken }),
  });
  const vendorId = payload?.vendor?.id || payload?.data?.vendor?.id;
  if (vendorId) {
    state.settings.vendorId = String(vendorId);
    syncSettingsToForm();
    saveState();
    setStatus(`غرفه شناسایی شد: ${vendorId}`);
  } else {
    setStatus("غرفه پیدا نشد");
  }
}

async function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function addRowWarning(row, message) {
  row.warnings = [...new Set([...(row.warnings || []), message].filter(Boolean))];
}

function imageEnhancementWarning(image) {
  if (!image?.enhancement_error) return "";
  return `ویرایش عکس «${image.filename || "product.jpg"}» انجام نشد: ${image.enhancement_error}`;
}

async function enhanceImage(dataUrl, filename) {
  if (!state.settings.openRouterKey) {
    return {
      dataUrl,
      model: "",
      error: "کلید هوش مصنوعی وارد نشده؛ عکس اصلی استفاده شد.",
    };
  }

  const selectedModel = state.settings.openRouterImageModel || DEFAULT_IMAGE_MODEL;
  const payload = await apiFetch("/api/ai/enhance-image", {
    method: "POST",
    body: JSON.stringify({
      openrouter_key: state.settings.openRouterKey,
      image_data_url: dataUrl,
      filename,
      model: selectedModel,
    }),
  });
  return {
    dataUrl: payload.enhanced_image_data_url || dataUrl,
    model: payload.model || selectedModel,
    error: payload.enhanced_image_data_url ? "" : "تصویر ویرایش‌شده دریافت نشد.",
  };
}

async function productImageFromFile(file) {
  const dataUrl = await fileToDataUrl(file);
  let enhancement = null;
  try {
    setStatus(`در حال آماده‌سازی عکس ${file.name}...`);
    enhancement = await enhanceImage(dataUrl, file.name);
  } catch (error) {
    enhancement = {
      dataUrl,
      model: state.settings.openRouterImageModel || DEFAULT_IMAGE_MODEL,
      error: error.message || "ویرایش عکس انجام نشد.",
    };
  }
  return {
    id: uid(),
    filename: file.name,
    original_image: dataUrl,
    enhanced_image: enhancement.dataUrl || dataUrl,
    use_enhanced: true,
    enhancement_model: enhancement.model || "",
    enhancement_error: enhancement.error || "",
  };
}

function createProductRow(images) {
  const normalizedImages = Array.isArray(images) ? images.filter(Boolean) : [];
  const imageWarnings = normalizedImages.map(imageEnhancementWarning).filter(Boolean);
  const row = {
    id: uid(),
    selected: true,
    filename: normalizedImages[0]?.filename || "product.jpg",
    images: normalizedImages,
    status: "Image Added",
    category_id: "",
    category_title: "",
    category_confidence: 0,
    name: "",
    brief: "",
    description: "",
    price_suggested: "",
    price_final: "",
    price_sample_count: 0,
    price_confidence: "",
    price_min: "",
    price_max: "",
    price_samples: [],
    price_criteria: {},
    analysis_runs: 0,
    analyzed_at: "",
    stock: state.settings.defaultStock || "1",
    sku: "",
    weight: "",
    package_weight: "",
    preparation_days: state.settings.defaultPreparationDays || "3",
    unit_quantity: "",
    unit_type: "",
    variants: [],
    attributes: {},
    warnings: imageWarnings,
    errors: [],
    field_errors: {},
    general_errors: [],
    product_id: "",
  };
  setRowStatusFromValidation(row);
  row.status = "Image Added";
  return row;
}

async function addFilesToRow(row, files) {
  if (!files.length) return;
  syncSettingsFromForm();
  normalizeRowImages(row);
  for (const file of files) {
    setStatus(`در حال آماده‌سازی عکس ${file.name}...`);
    const productImage = await productImageFromFile(file);
    row.images.push(productImage);
    addRowWarning(row, imageEnhancementWarning(productImage));
  }
  setRowStatusFromValidation(row);
  saveState();
  render();
  setStatus("عکس به محصول اضافه شد");
}

async function addFiles(files) {
  syncSettingsFromForm();
  if (!files.length) return;
  const createdRows = [];
  for (const file of files) {
    setStatus(`در حال آماده‌سازی عکس ${file.name}...`);
    const productImage = await productImageFromFile(file);
    const row = createProductRow([productImage]);
    state.rows.push(row);
    createdRows.push(row);
  }
  if (createdRows.length) {
    mobileState.activeRowId = createdRows[0].id;
    mobileState.step = 0;
  }
  saveState();
  render();
  setStatus(createdRows.length > 1 ? `${createdRows.length} محصول اضافه شد` : "عکس محصول اضافه شد");
}

async function analyzeRow(rowId) {
  syncSettingsFromForm();
  await loadCategories(false);
  const row = state.rows.find((item) => item.id === rowId);
  if (!row) return;
  row.status = "Analyzing";
  row.errors = [];
  row.general_errors = [];
  saveState();
  render();
  try {
    const categories = state.categories
      .filter((item) => item.is_leaf)
      .map((item) => ({ id: item.id, title: item.path || item.title, unit_type: item.unit_type || null }));
    const analysis = await apiFetch("/api/ai/analyze", {
      method: "POST",
      body: JSON.stringify({
        openrouter_key: state.settings.openRouterKey,
        image_data_url: selectedImage(row),
        categories,
        model: state.settings.openRouterModel || "google/gemini-2.5-flash",
      }),
    });
    applyAnalysis(row, analysis);
    if (row.category_id) await ensureAttributes(row.category_id);
    applyAttributeGuesses(row, analysis.attributes || []);
    await suggestPrice(row.id, false);
    row.analysis_runs = Number(row.analysis_runs || 0) + 1;
    row.analyzed_at = new Date().toISOString();
    setRowStatusFromValidation(row);
    saveState();
    render();
    setStatus("اطلاعات محصول آماده شد");
  } catch (error) {
    row.status = "Failed";
    row.errors = [];
    row.general_errors = [error.message];
    saveState();
    render();
    setStatus(error.message);
  }
}

function applyAnalysis(row, analysis) {
  row.name = analysis.title || row.name;
  row.brief = analysis.brief || row.brief;
  row.description = analysis.description || row.description;
  row.warnings = Array.isArray(analysis.warnings) ? analysis.warnings : [];
  const categoryId = analysis.category?.id;
  if (categoryId) {
    const category = categoryById(categoryId);
    row.category_id = categoryId;
    row.category_title = category?.title || analysis.category?.title || "";
    row.category_confidence = Number(analysis.category?.confidence || 0);
    applyCategoryUnit(row, category);
  }
  const weight = analysis.estimated_weight || {};
  if (!row.weight && Number(weight.confidence || 0) >= 0.5 && weight.value) {
    const weightInGrams = weightValueInGrams(weight);
    if (weightInGrams !== null) row.weight = String(Math.round(weightInGrams));
  }
  applyEstimatedPackageWeight(row, analysis);
  applySaleUnit(row, analysis);
}

function applyAttributeGuesses(row, guesses) {
  const attrs = requiredAttributesForCategory(row.category_id);
  row.attributes = row.attributes || {};
  for (const guess of guesses) {
    if (!guess.value) continue;
    let attr = attrs.find((item) => String(item.id) === String(guess.attribute_id));
    if (!attr && guess.title) {
      attr = attrs.find((item) => String(item.title).trim() === String(guess.title).trim());
    }
    if (attr && Number(guess.confidence || 0) >= 0.45) {
      row.attributes[attr.id] = guess.value;
    }
  }
}

async function suggestPrice(rowId, rerender = true) {
  syncSettingsFromForm();
  const row = state.rows.find((item) => item.id === rowId);
  if (!row) return;
  const previousPriceWarnings = new Set(row.price_warnings || []);
  const query = priceQueryForRow(row);
  if (!query) {
    row.errors = ["برای پیشنهاد قیمت، نام محصول را وارد کنید."];
    setRowStatusFromValidation(row);
    saveState();
    if (rerender) render();
    return;
  }
  try {
    const payload = await apiFetch("/api/basalam/price-suggestion", {
      method: "POST",
      body: JSON.stringify({
        token: state.settings.basalamToken || null,
        q: query,
        name: row.name || null,
        category_id: row.category_id ? Number(row.category_id) : null,
        category_title: row.category_title || null,
        weight: numberOrNull(row.weight),
        unit_quantity: numberOrNull(row.unit_quantity),
        unit_type: validUnitType(row.unit_type),
        rows: 80,
      }),
    });
    row.price_suggested = payload.suggested_price || "";
    row.price_sample_count = payload.sample_count || 0;
    row.price_confidence = payload.confidence || "";
    row.price_min = payload.min_price || "";
    row.price_max = payload.max_price || "";
    row.price_samples = Array.isArray(payload.samples) ? payload.samples : [];
    row.price_criteria = payload.criteria || {};
    row.price_warnings = payload.warnings || [];
    if (!row.price_final && payload.suggested_price) {
      row.price_final = String(payload.suggested_price);
    }
    row.warnings = [
      ...new Set([...(row.warnings || []).filter((warning) => !previousPriceWarnings.has(warning)), ...row.price_warnings]),
    ];
    setRowStatusFromValidation(row);
    saveState();
    if (rerender) render();
  } catch (error) {
    row.warnings = [...(row.warnings || []), error.message];
    setRowStatusFromValidation(row);
    saveState();
    if (rerender) render();
  }
}

function buildProductPayload(row) {
  const attrs = requiredAttributesForCategory(row.category_id);
  const productAttribute = attrs
    .map((attr) => ({
      attribute_id: Number(attr.id),
      value: row.attributes?.[attr.id],
    }))
    .filter((item) => item.value);

  const unitQuantity = numberOrNull(row.unit_quantity);
  const unitType = validUnitType(row.unit_type);
  const payload = {
    name: row.name,
    brief: row.brief,
    description: row.description,
    category_id: Number(row.category_id),
    primary_price: Number(row.price_final),
    stock: Number(row.stock),
    preparation_days: numberOrNull(row.preparation_days),
    weight: numberOrNull(row.weight),
    package_weight: packageWeightForRow(row),
    product_attribute: productAttribute,
    sku: row.sku,
  };
  if (unitQuantity !== null && unitType) {
    payload.unit_quantity = unitQuantity;
    payload.unit_type = unitType;
  }
  const variants = normalizedVariants(row).map((variant) => ({
    primary_price: variant.primary_price,
    stock: variant.stock,
    properties: variant.properties,
  }));
  if (variants.length) {
    payload.variants = variants;
  }
  payload.status = Number(DEFAULT_PRODUCT_STATUS);
  return removeEmpty(payload);
}

function removeEmpty(value) {
  if (Array.isArray(value)) {
    return value.map(removeEmpty).filter((item) => item !== null && item !== undefined && item !== "");
  }
  if (value && typeof value === "object") {
    const output = {};
    for (const [key, child] of Object.entries(value)) {
      const cleaned = removeEmpty(child);
      if (cleaned === null || cleaned === undefined || cleaned === "") continue;
      if (Array.isArray(cleaned) && cleaned.length === 0) continue;
      if (typeof cleaned === "object" && !Array.isArray(cleaned) && Object.keys(cleaned).length === 0) continue;
      output[key] = cleaned;
    }
    return output;
  }
  return value;
}

function buildSubmissionPreview(row) {
  return {
    action: row.product_id ? "update" : "create",
    price_unit: PRICE_UNIT,
    vendor_id: Number(state.settings.vendorId),
    product_id: row.product_id || null,
    images: selectedProductImages(row).map((image, index) => ({
      order: index + 1,
      primary: index === 0,
      filename: image.filename,
    })),
    product: buildProductPayload(row),
  };
}

function openSubmitDialog(rowId) {
  syncSettingsFromForm();
  const row = state.rows.find((item) => item.id === rowId);
  if (!row) return;
  setRowStatusFromValidation(row);
  if (row.errors.length) {
    saveState();
    render();
    setStatus("موارد مشخص‌شده را کامل کنید و دوباره ثبت کنید");
    return;
  }
  pendingSubmitRowId = rowId;
  els.payloadPreview.textContent = JSON.stringify(buildSubmissionPreview(row), null, 2);
  els.submitDialog.showModal();
}

async function submitRow(rowId) {
  syncSettingsFromForm();
  const row = state.rows.find((item) => item.id === rowId);
  if (!row) return;
  row.status = "Submitting";
  row.errors = [];
  row.general_errors = [];
  saveState();
  render();
  try {
    const response = await apiFetch("/api/basalam/submit-product", {
      method: "POST",
      body: JSON.stringify({
        token: state.settings.basalamToken,
        vendor_id: Number(state.settings.vendorId),
        product_id: row.product_id ? Number(row.product_id) : null,
        images: selectedProductImages(row),
        product: buildProductPayload(row),
      }),
    });
    row.status = "Submitted";
    row.general_errors = [];
    row.product_id = row.product_id || response?.product?.id || response?.product?.data?.id || "";
    row.submission = response;
    saveState();
    render();
    setStatus(response?.mode === "update" ? "محصول ویرایش شد" : "محصول در غرفه ثبت شد");
  } catch (error) {
    row.status = "Failed";
    row.errors = [];
    row.field_errors = {};
    applyProviderErrors(row, error);
    saveState();
    render();
    setStatus(error.message);
  }
}

function deleteRow(rowId) {
  const index = state.rows.findIndex((row) => row.id === rowId);
  if (index >= 0) {
    state.rows.splice(index, 1);
    saveState();
    render();
  }
}

function syncSettingsPanelForViewport() {
  if (!els.settingsPanel) return;
  syncingSettingsPanel = true;
  if (mobileMedia.matches) {
    if (!settingsPanelTouched) els.settingsPanel.open = false;
  } else {
    els.settingsPanel.open = true;
  }
  queueMicrotask(() => {
    syncingSettingsPanel = false;
  });
}

function bindEvents() {
  if (els.settingsPanel) {
    els.settingsPanel.addEventListener("toggle", () => {
      if (!syncingSettingsPanel && mobileMedia.matches) settingsPanelTouched = true;
    });
  }
  if (mobileMedia.addEventListener) {
    mobileMedia.addEventListener("change", syncSettingsPanelForViewport);
  } else {
    mobileMedia.addListener(syncSettingsPanelForViewport);
  }
  els.saveSettingsBtn.addEventListener("click", () => {
    syncSettingsFromForm();
    setStatus("ذخیره شد");
  });
  els.verifyTokenBtn.addEventListener("click", () => {
    verifyToken().catch((error) => setStatus(error.message));
  });
  els.loadCategoriesBtn.addEventListener("click", () => {
    syncSettingsFromForm();
    loadCategories(true).catch((error) => setStatus(error.message));
  });
  els.clearDataBtn.addEventListener("click", () => {
    if (!confirm("اطلاعات ذخیره‌شده در این مرورگر پاک شود؟")) return;
    localStorage.removeItem(STORAGE_KEY);
    window.location.reload();
  });
  els.imageInput.addEventListener("change", async () => {
    await addFiles(Array.from(els.imageInput.files || []));
    els.imageInput.value = "";
  });
  els.confirmSubmitBtn.addEventListener("click", async () => {
    const rowId = pendingSubmitRowId;
    pendingSubmitRowId = null;
    els.submitDialog.close();
    if (rowId) await submitRow(rowId);
  });
  els.imagePreviewDialog.addEventListener("close", () => {
    els.imagePreviewImg.removeAttribute("src");
  });
}

loadState();
syncSettingsToForm();
bindEvents();
syncSettingsPanelForViewport();
render();
loadCategories(false).catch(() => {});
