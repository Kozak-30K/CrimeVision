"use strict";



document.addEventListener("DOMContentLoaded", () => {

  const state = {

    activeView: "image",

    cases: [],

    activeCaseId: "",

    currentResults: {

      image: null,

      audio: {

        transcription: null,

        events: null,

        semantic: null,

        timeline: null

      },

      video: null

    }

  };



  const $ = (selector, root = document) => root.querySelector(selector);

  const $$ = (selector, root = document) =>

    Array.from(root.querySelectorAll(selector));



  const viewConfig = {

    image: {

      title: "Image Analysis",

      description: "Examine image evidence using object detection and scene analysis."

    },

    audio: {

      title: "Audio Analysis",

      description: "Transcribe audio and extract events, semantic information, and timelines."

    },

    video: {

      title: "Video Analysis",

      description: "Analyze video evidence using sampled frames and object detection."

    },

    investigations: {

      title: "Investigations",

      description: "Manage investigations, registered evidence, and analysis records."

    },

    reports: {

      title: "Reports",

      description: "Review saved analysis records associated with investigations."

    }

  };



  function showNotice(message, type = "info") {

    const notice = $("#notice");

    if (!notice) return;



    notice.textContent = message;

    notice.className = `notice ${type}`;

    notice.hidden = false;

  }



  function clearNotice() {

    const notice = $("#notice");

    if (!notice) return;



    notice.textContent = "";

    notice.hidden = true;

  }



  function setStatus(element, message, type = "") {

    if (!element) return;



    element.textContent = message;

    element.className = "status-message";



    if (type) element.classList.add(type);

  }



  async function apiRequest(url, options = {}) {

    const response = await fetch(url, options);

    const contentType = response.headers.get("content-type") || "";



    let payload;



    if (contentType.includes("application/json")) {

      payload = await response.json();

    } else {

      payload = await response.text();

    }



    if (!response.ok) {

      const message =

        payload && typeof payload === "object"

          ? payload.error || payload.message

          : payload;



      throw new Error(

        message || `Request failed with HTTP ${response.status}.`

      );

    }



    return payload;

  }





function renderResult(container, data) {

  if (!container) return;



  container.replaceChildren();



  const element = (tag, className, text) => {

    const node = document.createElement(tag);

    if (className) node.className = className;

    if (text !== undefined) node.textContent = String(text);

    return node;

  };



  const section = (title) => {

    const wrapper = element("section", "analysis-section");

    wrapper.appendChild(element("h3", "analysis-section-title", title));

    container.appendChild(wrapper);

    return wrapper;

  };



  const metric = (parent, label, value) => {

    const card = element("div", "metric-card");

    card.append(

      element("span", "metric-label", label),

      element("strong", "metric-value", value)

    );

    parent.appendChild(card);

  };



  const showImage = (parent, title, url, alt) => {

    const wrapper = element("div", "evidence-image-card");

    wrapper.appendChild(element("h4", "", title));



    const image = element("img", "evidence-result-image");

    image.alt = alt;

    image.loading = "lazy";

    image.src = url;



    image.addEventListener("error", () => {

      image.hidden = true;

      wrapper.appendChild(

        element("p", "inline-error", "Image preview could not be loaded.")

      );

    }, { once: true });



    wrapper.appendChild(image);

    parent.appendChild(wrapper);

  };



  const showTechnicalDetails = () => {};



  const renderDetection = (result) => {

    const summary = section("Detection summary");

    const metrics = element("div", "metrics-grid");



    metric(metrics, "Objects detected", result.detection_count ?? result.detections?.length ?? 0);

    metric(metrics, "People predictions", result.people_count ?? 0);

    metric(metrics, "Model", result.model || "Not reported");

    metric(metrics, "Device", result.device || "Not reported");



    summary.appendChild(metrics);



    const detections = Array.isArray(result.detections) ? result.detections : [];

    const objectsSection = section("Detected objects");



    if (!detections.length) {

      objectsSection.appendChild(

        element("p", "empty-state", "No objects were detected at the configured threshold.")

      );

    } else {

      const list = element("div", "detection-list");



      detections.forEach((detection, index) => {

        const card = element("article", "detection-card");

        const header = element("div", "detection-card-header");

        const label = element("h4", "", detection.label || "Unknown object");

        const confidence = Number(detection.confidence);

        const confidenceText = Number.isFinite(confidence)

          ? `${(confidence * 100).toFixed(1)}%`

          : "Not reported";



        header.append(

          label,

          element("strong", "detection-confidence", confidenceText)

        );



        card.appendChild(header);



        if (Number.isFinite(confidence)) {

          const track = element("div", "confidence-track");

          const fill = element("div", "confidence-fill");

          fill.style.width = `${Math.max(0, Math.min(100, confidence * 100))}%`;

          track.appendChild(fill);

          card.appendChild(track);

        }



        const bbox = detection.bbox_xyxy;

        if (bbox) {

          card.appendChild(

            element(

              "p",

              "detection-coordinates",

              `Bounding box: (${bbox.x1}, ${bbox.y1}) → (${bbox.x2}, ${bbox.y2})`

            )

          );

        }



        card.appendChild(

          element("p", "record-meta", `Detection ${index + 1} · Class ID: ${detection.class_id ?? "—"}`)

        );



        list.appendChild(card);

      });



      objectsSection.appendChild(list);

    }



    const limitations = result.limitations;

    if (Array.isArray(limitations) && limitations.length) {

      const note = section("Interpretation and limitations");

      const list = element("ul", "limitation-list");



      limitations.forEach((item) => {

        list.appendChild(element("li", "", item));

      });



      note.appendChild(list);

    }



    const width = result.image_dimensions?.width;

    const height = result.image_dimensions?.height;



    const details = {

      analysis_type: result.analysis_type,

      source_image: result.source_image,

      image_dimensions: result.image_dimensions,

      model: result.model,

      device: result.device,

      confidence_threshold: result.confidence_threshold,

      analyzed_at_utc: result.analyzed_at_utc,

      annotated_image: result.annotated_image,

      json_output: result.json_output

    };



    if (width && height) {

      const metadata = section("Evidence metadata");

      const grid = element("div", "metrics-grid");

      metric(grid, "Image dimensions", `${width} × ${height}`);

      metric(grid, "Confidence threshold", `${(Number(result.confidence_threshold ?? 0) * 100).toFixed(0)}%`);

      metric(grid, "Source file", result.source_image || "Not reported");

      metadata.appendChild(grid);

    }



  };



  const renderDescription = (result) => {

    const descriptionSection = section("Scene description");

    const description =

      result.scene_description ??

      result.description ??

      result.caption ??

      result.summary;



    if (typeof description === "string") {

      descriptionSection.appendChild(

        element("p", "scene-description-text", description)

      );

    } else if (description !== undefined) {

      const text = typeof description === "object"

        ? [description.summary, description.description, description.caption,

           description.text, description.scene]

            .filter(value => typeof value === "string" && value.trim())

            .join(" ")

        : String(description);

      descriptionSection.appendChild(

        element("p", "scene-description-text",

          text || "No readable scene description was returned.")

      );

    } else {

      descriptionSection.appendChild(

        element("p", "empty-state", "The response did not contain a recognized description field.")

      );

    }

  };



  const renderCombined = (result) => {

    const heading = section("Combined image analysis");

    heading.appendChild(

      element(

        "p",

        "forensic-notice",

        result.notice || "AI-generated preliminary analysis. Verify findings against the original evidence."

      )

    );



    if (result.object_detection) {

      const detection = result.object_detection;

      if (detection.annotated_image) {

        const filename = String(detection.annotated_image).split(/[\\/]/).pop();

        const imageRow = element("div", "evidence-image-grid");

        const originalFile = $("#image-file")?.files?.[0];

        if (originalFile) {

          const originalUrl = URL.createObjectURL(originalFile);

          showImage(imageRow, "Original evidence", originalUrl, "Original uploaded image evidence");

          // Keep the object URL alive while the result is displayed.

        }

        showImage(imageRow, "Annotated detections", `/api/detection-output/${encodeURIComponent(filename)}`, "Annotated image with object detection boxes");

        container.appendChild(imageRow);

      }

      renderDetection(detection);

    }

    if (result.scene_description) renderDescription(result.scene_description);



    showTechnicalDetails(container, result);

  };



  if (data && typeof data === "object" && !Array.isArray(data)) {

    if (data.analysis_type === "multimodal_image_analysis") {

      renderCombined(data);

      return;

    }



    if (Array.isArray(data.detections) || data.analysis_type === "object_detection") {

      const title = element("h3", "analysis-result-heading", "Object detection results");

      container.appendChild(title);



      if (data.annotated_image) {

        const filename = data.annotated_image.split(/[\\/]/).pop();

        const safeFilename = encodeURIComponent(filename);



        const imageRow = element("div", "evidence-image-grid");



        showImage(

          imageRow,

          "Annotated image",

          `/api/detection-output/${safeFilename}`,

          "Annotated image with model detection boxes"

        );



        container.appendChild(imageRow);

      }



      renderDetection(data);

      showTechnicalDetails(container, data);

      return;

    }



    if (

      data.scene_description !== undefined ||

      data.description !== undefined ||

      data.caption !== undefined ||

      data.summary !== undefined

    ) {

      renderDescription(data);

      showTechnicalDetails(container, data);

      return;

    }

  }



  const fallbackText = typeof data === "string"

    ? data

    : [data?.message, data?.summary, data?.description, data?.caption, data?.error]

        .find(value => typeof value === "string" && value.trim());



  if (fallbackText) {

    container.appendChild(element("p", "scene-description-text", fallbackText));

  } else {

    container.appendChild(

      element("p", "empty-state",

        "Analysis returned data, but no readable summary was available.")

    );

  }

}





  function renderEmpty(container, message) {

    if (!container) return;



    container.replaceChildren();



    const paragraph = document.createElement("p");

    paragraph.className = "empty-state";

    paragraph.textContent = message;



    container.appendChild(paragraph);

  }



  function getActiveCaseId() {

    return state.activeCaseId || $("#case-select")?.value || "";

  }



  function navigateTo(viewName) {

    if (!viewConfig[viewName]) return;



    state.activeView = viewName;



    $$("[data-view]").forEach((button) => {

      const active = button.dataset.view === viewName;

      button.classList.toggle("active", active);

      button.setAttribute("aria-current", active ? "page" : "false");

    });



    Object.keys(viewConfig).forEach((name) => {

      const section = $(`#view-${name}`);

      if (section) section.hidden = name !== viewName;

    });



    const config = viewConfig[viewName];



    if ($("#page-title")) $("#page-title").textContent = config.title;

    if ($("#breadcrumb-current")) {

      $("#breadcrumb-current").textContent = config.title;

    }

    if ($("#page-description")) {

      $("#page-description").textContent = config.description;

    }



    clearNotice();



    if (viewName === "investigations") loadInvestigations();

    if (viewName === "reports") loadReports();

  }



  async function loadCases() {

    const select = $("#case-select");

    if (!select) return;



    try {

      const payload = await apiRequest("/api/cases");

      const cases = Array.isArray(payload)

        ? payload

        : Array.isArray(payload.cases)

          ? payload.cases

          : [];



      state.cases = cases;



      const previousId = getActiveCaseId();



      select.replaceChildren();



      const defaultOption = document.createElement("option");

      defaultOption.value = "";

      defaultOption.textContent = "Select investigation";

      select.appendChild(defaultOption);



      cases.forEach((item) => {

        const option = document.createElement("option");

        option.value = item.id ?? item.case_id ?? "";

        option.textContent =

          item.title || item.name || `Investigation ${option.value}`;



        select.appendChild(option);

      });



      const matchingCase = cases.find(

        (item) => String(item.id ?? item.case_id ?? "") === String(previousId)

      );



      if (matchingCase) {

        select.value = String(matchingCase.id ?? matchingCase.case_id);

      }



      state.activeCaseId = select.value;



      renderInvestigationList();

    } catch (error) {

      showNotice(`Could not load investigations: ${error.message}`, "error");

    }

  }



  async function createCase(event) {

    event.preventDefault();



    const title = $("#new-case-title")?.value.trim();

    const description = $("#new-case-description")?.value.trim();

    const status = $("#new-case-status")?.value;



    if (!title) {

      showNotice("Enter an investigation title first.", "error");

      return;

    }



    const submitButton = $("#create-case-submit");

    if (submitButton) submitButton.disabled = true;



    try {

      const payload = { title, description };



      if (status) payload.status = status;



      const result = await apiRequest("/api/cases", {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify(payload)

      });



      const createdCase = result.case || result;

      const createdId = createdCase.id ?? createdCase.case_id;



      await loadCases();



      if (createdId != null && $("#case-select")) {

        $("#case-select").value = String(createdId);

        state.activeCaseId = String(createdId);

      }



      $("#new-case-dialog")?.close();

      $("#new-case-form")?.reset();



      showNotice("Investigation created successfully.", "success");

      await loadInvestigations();

    } catch (error) {

      showNotice(`Could not create investigation: ${error.message}`, "error");

    } finally {

      if (submitButton) submitButton.disabled = false;

    }

  }



  function renderInvestigationList() {

    const container = $("#investigation-list");

    if (!container) return;



    container.replaceChildren();



    if (!state.cases.length) {

      renderEmpty(container, "No investigations found. Create one to get started.");

      return;

    }



    state.cases.forEach((item) => {

      const id = item.id ?? item.case_id ?? "";

      const card = document.createElement("article");

      card.className = "investigation-card";



      const heading = document.createElement("h3");

      heading.textContent = item.title || item.name || `Investigation ${id}`;



      const details = document.createElement("p");

      details.textContent = item.description || "No description provided.";



      const metadata = document.createElement("p");

      metadata.className = "record-meta";

      metadata.textContent =

        `Status: ${item.status || "Unknown"} · ` +

        `Evidence: ${item.evidence_count ?? 0} · ` +

        `Analyses: ${item.analysis_count ?? 0}`;



      const openButton = document.createElement("button");

      openButton.type = "button";

      openButton.className = "button button-secondary";

      openButton.textContent = "Select investigation";



      openButton.addEventListener("click", () => {

        const select = $("#case-select");

        if (select) select.value = String(id);



        state.activeCaseId = String(id);

        showNotice(`Selected: ${heading.textContent}`, "success");

      });



      card.append(heading, details, metadata, openButton);

      container.appendChild(card);

    });

  }









  async function loadInvestigations() {
    const caseId = getActiveCaseId();
    const evidenceContainer = $("#evidence-list");

    const analysisContainer = $("#case-analysis-list");

    if (!caseId) {
      renderEmpty(evidenceContainer, "Select an investigation to view its evidence.");
      renderEmpty(analysisContainer, "Select an investigation to view saved analyses.");
      return;
    }

    try {

      const [evidencePayload, analysisPayload] = await Promise.all([

        apiRequest(`/api/cases/${encodeURIComponent(caseId)}/evidence`),

        apiRequest(`/api/cases/${encodeURIComponent(caseId)}/analyses`)

      ]);



      renderRecordList(

        evidenceContainer,

        evidencePayload.evidence || [],

        "No evidence registered for this investigation."

      );



      renderRecordList(

        analysisContainer,

        analysisPayload.analyses || [],

        "No saved analyses for this investigation."

      );

    } catch (error) {

      showNotice(`Could not load investigation records: ${error.message}`, "error");

    }

  }



  
function renderRecordList(container, records, emptyMessage) {
  if (!container) return;

  container.replaceChildren();

  if (!records.length) {
    renderEmpty(container, emptyMessage);
    return;
  }

  const isEvidenceList = container.id === "evidence-list";

  records.forEach((record) => {
    const card = document.createElement("article");
    card.className = "record-card";

    const heading = document.createElement("h3");
    heading.textContent =
      record.original_filename ||
      record.metadata?.original_filename ||
      record.filename ||
      record.title ||
      record.name ||
      record.analysis_type ||
      "Evidence record";

    const metadata = document.createElement("p");
    metadata.className = "record-meta";
    metadata.textContent = [
      record.modality,
      record.status,
      record.created_at || record.registered_at_utc
    ].filter(Boolean).join(" · ") || "Record details available";

    card.append(heading, metadata);

    if (isEvidenceList) {
      const evidenceId = record.evidence_id;
      const modality = String(record.modality || "").toLowerCase();

      if (evidenceId && ["image", "video", "audio"].includes(modality)) {
        const fileUrl =
          `/api/evidence/${encodeURIComponent(evidenceId)}/file`;

        let preview;

        if (modality === "image") {
          preview = document.createElement("img");
          preview.alt = heading.textContent;
          preview.loading = "lazy";
          preview.className = "stored-evidence-preview";
        } else {
          preview = document.createElement(
            modality === "video" ? "video" : "audio"
          );
          preview.controls = true;
          preview.preload = "metadata";
          preview.className = "stored-evidence-player";
        }

        preview.src = fileUrl;

        preview.addEventListener("error", () => {
          preview.hidden = true;
          const error = document.createElement("p");
          error.textContent =
            "Preview unavailable. Check that the original file exists.";
          card.appendChild(error);
        }, { once: true });

        card.appendChild(preview);

        const download = document.createElement("a");
        download.href = `${fileUrl}?download=1`;
        download.textContent = "Download original evidence";
        download.className = "record-action";
        download.setAttribute("download", "");
        card.appendChild(download);
      } else {
        const unavailable = document.createElement("p");
        unavailable.textContent =
          "File preview unavailable: evidence identifier or modality is missing.";
        card.appendChild(unavailable);
      }
    } else {
      const resultId = record.result_id;

      if (resultId) {
        const viewButton = document.createElement("button");
        viewButton.type = "button";
        viewButton.textContent = "View saved analysis";
        viewButton.className = "record-action";

        const resultContainer = document.createElement("div");

        viewButton.addEventListener("click", async () => {
          viewButton.disabled = true;
          viewButton.textContent = "Loading analysis…";

          try {
            const payload = await apiRequest(
              `/api/analyses/${encodeURIComponent(resultId)}`
            );

            const analysis = payload.analysis;
            if (!analysis) {
              throw new Error("Saved analysis was not returned.");
            }

            resultContainer.replaceChildren();

            const output = document.createElement("pre");
            output.className = "saved-analysis-output";
            output.textContent = JSON.stringify(
              analysis.result,
              null,
              2
            );

            resultContainer.appendChild(output);
            viewButton.textContent = "Refresh saved analysis";
          } catch (error) {
            viewButton.textContent = "Retry loading analysis";
            showNotice(
              `Could not open saved analysis: ${error.message}`,
              "error"
            );
          } finally {
            viewButton.disabled = false;
          }
        });

        card.append(viewButton, resultContainer);
      } else {
        const unavailable = document.createElement("p");
        unavailable.textContent =
          "This record has no saved result identifier.";
        card.appendChild(unavailable);
      }
    }

    container.appendChild(card);
  });
}




  async function loadReports() {

    const container = $("#report-list");
    if (!container) return;
    container.replaceChildren();
    const cases = state.cases;
    if (!cases.length) {
      await loadCases();
    }
    if (!state.cases.length) {
    renderEmpty(container, "No investigations are available yet.");
      return;}



    const heading = document.createElement("p");
    heading.className = "empty-state";
    heading.textContent ="Saved analysis records are listed by investigation below.";
    container.appendChild(heading);



    for (const item of state.cases) {

      const id = item.id ?? item.case_id;

      if (id == null) continue;



      const section = document.createElement("section");

      section.className = "report-group";



      const title = document.createElement("h3");

      title.textContent = item.title || `Investigation ${id}`;

      section.appendChild(title);



      try {

        const payload = await apiRequest(

          `/api/cases/${encodeURIComponent(id)}/analyses`

        );



        const records = payload.analyses || [];



        if (!records.length) {

          const empty = document.createElement("p");

          empty.textContent = "No saved analyses.";

          section.appendChild(empty);

        } else {

          records.forEach((record) => {

            const entry = document.createElement("article");

            entry.className = "record-card";



            const name = document.createElement("h4");

            name.textContent =

              record.analysis_type || record.title || "Analysis record";



            const details = document.createElement("p");

            details.textContent =

              record.created_at || record.status || "Saved analysis";



            entry.append(name, details);

            section.appendChild(entry);

          });

        }

      } catch (error) {

        const message = document.createElement("p");

        message.textContent = `Unable to load records: ${error.message}`;

        section.appendChild(message);

      }



      container.appendChild(section);

    }

  }



  function setupNavigation() {

    $$("[data-view]").forEach((button) => {

      button.addEventListener("click", () => {

        navigateTo(button.dataset.view);

      });

    });



    $("#case-select")?.addEventListener("change", (event) => {

      state.activeCaseId = event.target.value;



      if (state.activeView === "investigations") loadInvestigations();

      if (state.activeView === "reports") loadReports();

    });



    $("#refresh-cases")?.addEventListener("click", loadCases);

    $("#investigation-refresh")?.addEventListener("click", loadInvestigations);

    $("#reports-refresh")?.addEventListener("click", loadReports);



    $("#new-case-button")?.addEventListener("click", () => {

      $("#new-case-dialog")?.showModal();

    });



    $("#close-case-dialog")?.addEventListener("click", () => {

      $("#new-case-dialog")?.close();

    });



    $("#cancel-case-dialog")?.addEventListener("click", () => {

      $("#new-case-dialog")?.close();

    });



    $("#new-case-form")?.addEventListener("submit", createCase);

  }



  function setupFilePreview(inputId, previewId, emptyId, metaId, allowedTypes) {

    const input = $(`#${inputId}`);

    const preview = $(`#${previewId}`);

    const empty = $(`#${emptyId}`);

    const meta = $(`#${metaId}`);



    if (!input) return;



    input.addEventListener("change", () => {

      const file = input.files?.[0];



      if (!file) {

        if (preview) {

          preview.hidden = true;

          if (preview.tagName === "IMG") preview.removeAttribute("src");

          if (preview.tagName === "VIDEO") preview.removeAttribute("src");

          if (preview.tagName === "AUDIO") preview.removeAttribute("src");

        }



        if (empty) empty.hidden = false;

        if (meta) meta.textContent = "";

        return;

      }



      if (allowedTypes && !allowedTypes.includes(file.type) &&

          !allowedTypes.some((type) => file.name.toLowerCase().endsWith(type))) {

        showNotice("This file type may not be supported. Check the accepted formats.", "error");

      }



      const sizeLabel = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;

      if (meta) meta.textContent = `${file.name} · ${sizeLabel}`;



      if (preview && ["IMG", "VIDEO", "AUDIO"].includes(preview.tagName)) {

        const objectUrl = URL.createObjectURL(file);

        preview.src = objectUrl;

        preview.hidden = false;



        if (empty) empty.hidden = true;



        preview.addEventListener("load", () => URL.revokeObjectURL(objectUrl), { once: true });

        preview.addEventListener("error", () => URL.revokeObjectURL(objectUrl), { once: true });

        preview.addEventListener("loadedmetadata", () => URL.revokeObjectURL(objectUrl), { once: true });

      }

    });

  }



  function setupAudioControls() {

    $("#audio-operation")?.addEventListener("change", (event) => {

      const operation = event.target.value;

      const existingInputs = $("#audio-existing-inputs");



      if (existingInputs) {

        existingInputs.hidden = operation === "full" || operation === "transcribe";

      }

    });



    $$("#audio-result-tabs [data-audio-result]").forEach((button) => {

      button.addEventListener("click", () => {

        const resultType = button.dataset.audioResult;



        $$("#audio-result-tabs [data-audio-result]").forEach((tab) => {

          const active = tab === button;

          tab.classList.toggle("active", active);

          tab.setAttribute("aria-selected", active ? "true" : "false");

        });



        const data = state.currentResults.audio[resultType];



        renderAudioResult(resultType, data);

      });

    });

  }



  function setupVideoControls() {

    $("#video-confidence")?.addEventListener("input", (event) => {

      const value = Number(event.target.value);



      if ($("#video-confidence-value")) {

        $("#video-confidence-value").textContent = value.toFixed(2);

      }

    });

  }



  function setupForms() {

    $("#image-form")?.addEventListener("submit", (event) => {

      event.preventDefault();

      handleImageAnalysis();

    });



    $("#audio-form")?.addEventListener("submit", (event) => {

      event.preventDefault();

      handleAudioAnalysis();

    });



    $("#video-form")?.addEventListener("submit", (event) => {

      event.preventDefault();

      handleVideoAnalysis();

    });

  }





async function handleImageAnalysis() {

  const form = $("#image-form");

  const fileInput = $("#image-file");

  const operation = $("#image-operation")?.value || "analyze";

  const submitButton = $("#image-submit");

  const status = $("#image-status");

  const results = $("#image-results");

  const resultState = $("#image-result-state");



  const file = fileInput?.files?.[0];



  if (!file) {

    setStatus(status, "Choose an image before starting analysis.", "error");

    return;

  }



  const allowedExtensions = [".jpg", ".jpeg", ".png", ".webp"];

  const filename = file.name.toLowerCase();



  if (!allowedExtensions.some((extension) => filename.endsWith(extension))) {

    setStatus(status, "Unsupported image format. Use JPG, JPEG, PNG, or WEBP.", "error");

    return;

  }



  if (file.size === 0) {

    setStatus(status, "The selected image is empty.", "error");

    return;

  }



  const endpointByOperation = {

    detect: "/api/detect",

    describe: "/api/describe",

    analyze: "/api/analyze"

  };



  const endpoint = endpointByOperation[operation];



  if (!endpoint) {

    setStatus(status, "Select a valid image analysis operation.", "error");

    return;

  }



  submitButton.disabled = true;

  submitButton.classList.add("loading");

  setStatus(status, "Preparing image analysis…");

  if (resultState) resultState.textContent = "Analysis in progress";

  renderEmpty(results, "Processing image evidence. Please wait.");



  try {

    const caseId = getActiveCaseId();
    let evidenceId = null;

    // Register evidence and retain its ID for the saved analysis.
    if (caseId) {
      setStatus(status, "Registering image with the selected investigation…");

      const evidenceForm = new FormData();
      evidenceForm.append("modality", "image");
      evidenceForm.append("image", file);

      const registration = await apiRequest(
        `/api/cases/${encodeURIComponent(caseId)}/evidence`,
        { method: "POST", body: evidenceForm }
      );

      evidenceId = registration.evidence?.evidence_id ?? null;
    }

    setStatus(status, "Running image analysis…");



    const analysisForm = new FormData();

    analysisForm.append("image", file);



    if ($("#image-notes")?.value.trim()) {

      analysisForm.append("notes", $("#image-notes").value.trim());

    }



    const data = await apiRequest(endpoint, {

      method: "POST",

      body: analysisForm

    });





state.currentResults.image = data;

renderResult(results, data);



// Persist the completed result when a case is selected.
    await saveAnalysisIfSelected(caseId, evidenceId, `image_${operation}`, data);

    if (resultState) resultState.textContent = "Analysis completed";



    setStatus(

      status,

      caseId

        ? "Analysis completed. Evidence was registered with the selected investigation."

        : "Analysis completed successfully.",

      "success"

    );



    // Refresh investigation records so the new evidence is visible.

    if (caseId) {

      await loadCases();



      if (state.activeView === "investigations") {

        await loadInvestigations();

      }



      if (state.activeView === "reports") {

        await loadReports();

      }

    }

  } catch (error) {

    if (resultState) resultState.textContent = "Analysis failed";

    setStatus(status, `Image analysis failed: ${error.message}`, "error");

    renderEmpty(results, "No successful analysis result is available.");

  } finally {

    submitButton.disabled = false;

    submitButton.classList.remove("loading");

  }

}





  function formatTime(seconds) {

    const value = Number(seconds);

    if (!Number.isFinite(value) || value < 0) return "Time unavailable";

    const mins = Math.floor(value / 60);

    const secs = (value % 60).toFixed(2).padStart(5, "0");

    return `${String(mins).padStart(2, "0")}:${secs}`;

  }



  function renderAudioResult(resultType, data) {

    const container = $("#audio-results");

    if (!container) return;

    if (!data) {

      renderEmpty(container, `No ${resultType} result is available yet.`);

      return;

    }

    container.replaceChildren();

    const addSection = (title) => {

      const section = document.createElement("section");

      section.className = "analysis-section";

      const heading = document.createElement("h3");

      heading.className = "analysis-section-title";

      heading.textContent = title;

      section.appendChild(heading);

      container.appendChild(section);

      return section;

    };

    const addText = (parent, text, className = "") => {

      const node = document.createElement("p");

      node.className = className;

      node.textContent = text == null ? "—" : String(text);

      parent.appendChild(node);

      return node;

    };



    if (resultType === "transcription") {

      const summary = addSection("Transcription");

      const metadata = document.createElement("div");

      metadata.className = "metrics-grid";

      [["Language", data.language || "Auto-detected"], ["Model", data.model || "Not reported"], ["Device", data.device || "Not reported"], ["Duration", `${Number(data.duration_seconds || 0).toFixed(2)} seconds`]].forEach(([label, value]) => {

        const card = document.createElement("div"); card.className = "metric-card";

        const small = document.createElement("span"); small.className = "metric-label"; small.textContent = label;

        const strong = document.createElement("strong"); strong.className = "metric-value"; strong.textContent = value;

        card.append(small, strong); metadata.appendChild(card);

      });

      summary.appendChild(metadata);

      addText(summary, data.transcript || "No transcript text was returned.", "transcript-text");

      if (Array.isArray(data.segments) && data.segments.length) {

        const segmentSection = addSection("Timestamped segments");

        const list = document.createElement("div"); list.className = "transcript-segments";

        data.segments.forEach((segment, index) => {

          const row = document.createElement("article"); row.className = "transcript-segment";

          const time = document.createElement("strong"); time.textContent = `${formatTime(segment.start)} – ${formatTime(segment.end)}`;

          const text = document.createElement("p"); text.textContent = segment.text || "";

          const number = document.createElement("span"); number.className = "record-meta"; number.textContent = `Segment ${index + 1}`;

          row.append(time, text, number); list.appendChild(row);

        });

        segmentSection.appendChild(list);

      }

      if (Array.isArray(data.limitations) && data.limitations.length) {

        const section = addSection("Limitations"); const list = document.createElement("ul"); list.className = "limitation-list";

        data.limitations.forEach((item) => { const li = document.createElement("li"); li.textContent = item; list.appendChild(li); }); section.appendChild(list);

      }

    } else {

      const section = addSection(({events:"Extracted events", semantic:"Semantic findings", timeline:"Unified timeline"})[resultType] || "Analysis result");

      const rows = Array.isArray(data.events) ? data.events : Array.isArray(data.timeline) ? data.timeline : Array.isArray(data.items) ? data.items : null;

      if (rows) {

        if (!rows.length) addText(section, "No items were returned.", "empty-state");

        rows.forEach((item, index) => {

          const card = document.createElement("article"); card.className = "transcript-segment";

          const heading = document.createElement("strong"); heading.textContent = item.event || item.label || item.title || item.type || `Item ${index + 1}`;

          card.appendChild(heading);

          const audioTimestamp = item.audio_timestamp || item.speech_timestamps?.[0] || item.timestamp_range || null;

          const startValue = item.start ?? item.timestamp ?? audioTimestamp?.start_seconds;

          const endValue = item.end ?? audioTimestamp?.end_seconds;

          const time = startValue != null ? `${formatTime(startValue)}${endValue != null ? ` – ${formatTime(endValue)}` : ""}` : "";

          if (time) addText(card, time, "record-meta");

          const detail = item.description || item.statement || item.text || item.summary || item.explanation;

          if (detail) addText(card, detail);

          if (Array.isArray(item.candidate_categories) && item.candidate_categories.length) addText(card, `Candidate categories: ${item.candidate_categories.join(", ")}`, "record-meta");

          const confidence = item.confidence;

          if (confidence != null && Number.isFinite(Number(confidence))) addText(card, `Confidence: ${(Number(confidence) * 100).toFixed(1)}%`, "record-meta");

          section.appendChild(card);

        });

      } else {

        const message = data.message || data.summary || data.description || data.error;

        addText(

          section,

          typeof message === "string" ? message : "",

          "No readable findings were returned for this analysis."

        );

      }

    }

  }





  async function registerEvidenceIfSelected(modality, file, fieldName) {

    const caseId = getActiveCaseId();



    if (!caseId) {

      return { caseId: "", evidenceId: null };

    }



    const form = new FormData();

    form.append("modality", modality);

    form.append(fieldName, file);



    const registration = await apiRequest(

      `/api/cases/${encodeURIComponent(caseId)}/evidence`,

      {

        method: "POST",

        body: form

      }

    );



    return {

      caseId,

      evidenceId: registration.evidence?.evidence_id ?? null

    };

  }





  async function saveAnalysisIfSelected(caseId, evidenceId, analysisType, result) {
    if (!caseId) return null;

    return apiRequest(
      `/api/cases/${encodeURIComponent(caseId)}/analyses`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          analysis_type: analysisType,
          evidence_id: evidenceId ?? null,
          result
        })
      }
    );
  }

  async function handleAudioAnalysis() {

    const file = $("#audio-file")?.files?.[0];

    const button = $("#audio-submit");

    const status = $("#audio-status");

    const resultState = $("#audio-result-state");

    const operation = $("#audio-operation")?.value || "full";

    const language = $("#audio-language")?.value || "";

    const results = $("#audio-results");

    const needsAudioFile = operation === "full" || operation === "transcribe";

    if (needsAudioFile && !file) { setStatus(status, "Choose an audio file for transcription.", "error"); return; }

    const allowed = [".mp3", ".m4a", ".wav", ".ogg", ".flac", ".webm"];

    if (file && !allowed.some((ext) => file.name.toLowerCase().endsWith(ext))) { setStatus(status, "Unsupported audio format.", "error"); return; }

    if (file && (!file.size || file.size > 25 * 1024 * 1024)) { setStatus(status, "Audio must be non-empty and no larger than 25 MB.", "error"); return; }

    button.disabled = true; button.classList.add("loading");

    if (resultState) resultState.textContent = "Analysis in progress";

    setStatus(status, "Preparing audio analysis…");

    try {

      const registration = file ? await registerEvidenceIfSelected("audio", file, "audio"): { caseId: "", evidenceId: null };



      const { caseId, evidenceId } = registration;



      const existingText = $("#audio-json-input")?.value.trim() || "";

      let existing = null;

      if (["events", "semantic", "timeline"].includes(operation)) {

        try { existing = JSON.parse(existingText); }

        catch (_) { throw new Error("Paste a valid JSON object in the existing-results field for this operation."); }

        if (!existing || typeof existing !== "object" || Array.isArray(existing)) throw new Error("Existing input must be a JSON object.");

      }

      if (operation === "transcribe" || operation === "full") {

        setStatus(status, "Transcribing audio locally with Whisper…");

        const form = new FormData(); form.append("audio", file); if (language) form.append("language", language);

        const transcription = await apiRequest("/api/transcribe", { method: "POST", body: form });

        state.currentResults.audio.transcription = transcription;

        renderAudioResult("transcription", transcription);

        if (operation === "full") {

          setStatus(status, "Extracting timestamped events…");

          const events = await apiRequest("/api/extract-events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(transcription) });

          state.currentResults.audio.events = events;

          setStatus(status, "Running semantic extraction…");

          try {

            const semantic = await apiRequest("/api/semantic-extract", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(transcription) });

            state.currentResults.audio.semantic = semantic;

            setStatus(status, "Building unified timeline…");

            const timeline = await apiRequest("/api/timeline", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ keyword_result: events, semantic_result: semantic }) });

            state.currentResults.audio.timeline = timeline;

          } catch (semanticError) {

            // Local transcription and event extraction remain usable when the optional external semantic service is unavailable.

            state.currentResults.audio.semantic = { status: "unavailable", error: semanticError.message, note: "Semantic extraction may require GROQ_API_KEY and network access." };

          }

          renderAudioResult("transcription", transcription);

          const activeTab = $("#audio-result-tabs .result-tab.active")?.dataset.audioResult || "transcription";

          renderAudioResult(activeTab, state.currentResults.audio[activeTab]);

        }

      } else if (operation === "events") {

        const events = await apiRequest("/api/extract-events", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(existing) });

        state.currentResults.audio.events = events; renderAudioResult("events", events);

      } else if (operation === "semantic") {

        const semantic = await apiRequest("/api/semantic-extract", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(existing) });

        state.currentResults.audio.semantic = semantic; renderAudioResult("semantic", semantic);

      } else if (operation === "timeline") {

        if (!existing.keyword_result || !existing.semantic_result) throw new Error("Timeline input JSON must include keyword_result and semantic_result objects.");

        const timeline = await apiRequest("/api/timeline", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(existing) });

        state.currentResults.audio.timeline = timeline; renderAudioResult("timeline", timeline);

      }

      // Save the completed audio findings as one case record.

const audioResults = state.currentResults.audio;



const audioResult = operation === "full"

  ? { ...audioResults }

  : operation === "transcribe"

    ? audioResults.transcription

    : operation === "events"

      ? audioResults.events

      : operation === "semantic"

        ? audioResults.semantic

        : audioResults.timeline;



await saveAnalysisIfSelected(

  caseId,

  evidenceId,

  `audio_${operation}`,

  audioResult

);

      if (resultState) resultState.textContent = "Analysis completed";

      setStatus(status, caseId ? "Audio processing completed. Evidence was registered with the selected investigation." : "Audio processing completed.", "success");

      if (caseId) { await loadCases(); if (state.activeView === "investigations") await loadInvestigations(); if (state.activeView === "reports") await loadReports(); }

    } catch (error) {

      if (resultState) resultState.textContent = "Analysis failed";

      setStatus(status, `Audio analysis failed: ${error.message}`, "error");

    } finally { button.disabled = false; button.classList.remove("loading"); }

  }



  function renderVideoResult(data) {

    const container = $("#video-results");

    if (!container) return;

    container.replaceChildren();



    const metadata = data.video_metadata || {};

    const analysis = data.analysis || {};

    const frames = Array.isArray(data.frames) ? data.frames : [];



    // Convert structured model output into readable text, never raw JSON.

    const humanize = (value) => {

      if (value == null || value === "") return "";

      if (typeof value === "string" || typeof value === "number" ||

          typeof value === "boolean") return String(value);

      if (Array.isArray(value)) {

        return value.map(humanize).filter(Boolean).join("; ");

      }

      if (typeof value === "object") {

        const preferred = [

          "summary", "description", "caption", "scene",

          "label", "name", "event", "activity", "text"

        ];

        const keys = Object.keys(value);

        const ordered = [

          ...preferred.filter(k => keys.includes(k)),

          ...keys.filter(k => !preferred.includes(k))

        ];

        return ordered.map(key => {

          const item = humanize(value[key]);

          if (!item || key.startsWith("_")) return "";

          const label = key.replace(/_/g, " ");

          return `${label.charAt(0).toUpperCase()}${label.slice(1)}: ${item}`;

        }).filter(Boolean).join("\n");

      }

      return "";

    };



    const addSection = (title) => {

      const section = document.createElement("section");

      section.className = "analysis-section";

      const heading = document.createElement("h3");

      heading.className = "analysis-section-title";

      heading.textContent = title;

      section.appendChild(heading);

      container.appendChild(section);

      return section;

    };



    const addText = (parent, value, fallback = "No description available.") => {

      const text = document.createElement("p");

      text.textContent = humanize(value) || fallback;

      parent.appendChild(text);

    };



    const summary = addSection("Video overview");

    const grid = document.createElement("div");

    grid.className = "metrics-grid";



    [

      ["Duration", `${Number(metadata.duration_seconds || 0).toFixed(1)} seconds`],

      ["Frames reviewed", metadata.sampled_frame_count ??

        analysis.analyzed_frame_count ?? frames.length],

      ["Resolution", metadata.width && metadata.height

        ? `${metadata.width} × ${metadata.height}` : "Not available"]

    ].forEach(([label, value]) => {

      const card = document.createElement("div");

      card.className = "metric-card";

      const name = document.createElement("span");

      name.className = "metric-label";

      name.textContent = label;

      const result = document.createElement("strong");

      result.className = "metric-value";

      result.textContent = value;

      card.append(name, result);

      grid.appendChild(card);

    });

    summary.appendChild(grid);



    if (data.scene_summary) {

  const section = addSection("Scene summary");

  const scene = data.scene_summary;



  const addDetail = (parent, label, value) => {

    if (value == null || value === "") return;



    const item = document.createElement("div");

    item.className = "record-meta";



    const heading = document.createElement("strong");

    heading.textContent = `${label}: `;



    const text = document.createElement("span");

    text.textContent = String(value);



    item.append(heading, text);

    parent.appendChild(item);

  };



  const addCategoryGroup = (parent, title, values, percentage = false) => {

    if (!values || typeof values !== "object" ||

        Array.isArray(values) || !Object.keys(values).length) return;



    const heading = document.createElement("h4");

    heading.textContent = title;

    parent.appendChild(heading);



    const list = document.createElement("ul");

    list.className = "limitation-list";



    Object.entries(values).forEach(([name, value]) => {

      const item = document.createElement("li");

      const number = Number(value);

      const display = percentage && Number.isFinite(number)

        ? `${(number * 100).toFixed(1)}%`

        : String(value);



      item.textContent =

        `${name.replace(/_/g, " ")}: ${display}`;

      list.appendChild(item);

    });



    parent.appendChild(list);

  };



  if (typeof scene === "string") {

    addText(section, scene);

  } else if (typeof scene === "object" && !Array.isArray(scene)) {

    addDetail(section, "Dominant category", scene.dominant_category);

    addDetail(section, "Frames classified", scene.classified_frame_count);



    addCategoryGroup(

      section, "Category counts", scene.category_counts

    );



    addCategoryGroup(

      section, "Category distribution",

      scene.category_distribution, true

    );



    addCategoryGroup(

      section, "Mean relative scores", scene.mean_relative_scores

    );



    if (Array.isArray(scene.frames_disagreeing_with_dominant) &&

        scene.frames_disagreeing_with_dominant.length) {

      const heading = document.createElement("h4");

      heading.textContent = "Frames requiring closer review";

      section.appendChild(heading);



      const list = document.createElement("ul");

      list.className = "limitation-list";



      scene.frames_disagreeing_with_dominant.forEach(frame => {

        const item = document.createElement("li");

        item.textContent =

          `Frame ${frame.frame_index ?? "—"} · ` +

          `${formatTime(frame.timestamp_seconds)} · ` +

          `Category: ${frame.category ?? "Unknown"}`;

        list.appendChild(item);

      });



      section.appendChild(list);

    }



    if (scene.interpretation_note) {

      addDetail(section, "Interpretation", scene.interpretation_note);

    }



    if (scene.requires_review) {

      addDetail(section, "Review status", "Manual review recommended");

    }

  } else {

    addText(section, scene);

  }

}



    if (Array.isArray(data.scene_changes) && data.scene_changes.length) {

      const section = addSection("Changes throughout the video");

      const list = document.createElement("div");

      list.className = "transcript-segments";



      data.scene_changes.forEach((change, index) => {

        const card = document.createElement("article");

        card.className = "transcript-segment";

        const heading = document.createElement("strong");

        const timestamp = change && typeof change === "object"

          ? (change.timestamp_seconds ?? change.timestamp ?? change.time) : null;

        heading.textContent = timestamp != null

          ? `At ${typeof formatTime === "function" ? formatTime(timestamp) : timestamp}`

          : `Observation ${index + 1}`;

        card.appendChild(heading);



        const description = { ...(

          change && typeof change === "object" ? change : { description: change }

        ) };

        ["timestamp_seconds", "timestamp", "time", "frame_index"].forEach(

          key => delete description[key]

        );

        addText(card, description, "A possible scene change was detected.");

        list.appendChild(card);

      });



      section.appendChild(list);

    }



    const frameSection = addSection(`Sampled frames (${frames.length})`);

    if (!frames.length) {

      const empty = document.createElement("p");

      empty.className = "empty-state";

      empty.textContent = "No video frames were available for review.";

      frameSection.appendChild(empty);

    }



    const frameGrid = document.createElement("div");

    frameGrid.className = "video-frame-grid";



    frames.forEach(frame => {

      const card = document.createElement("article");

      card.className = "video-frame-card";



      const img = document.createElement("img");

      img.className = "video-frame-image";

      img.loading = "lazy";

      img.alt = `Video frame at ${formatTime(frame.timestamp_seconds)}`;



      const relative = String(frame.frame_path || "").replace(/^[\\/]+/, "");

      if (relative.startsWith("evidence/video/") &&

          !relative.split("/").includes("..")) {

        img.src = `/api/video-frame/${relative.split("/").map(encodeURIComponent).join("/")}`;

        img.addEventListener("error", () => {

          img.hidden = true;

          const note = document.createElement("p");

          note.className = "record-meta";

          note.textContent = "Frame preview could not be loaded.";

          card.insertBefore(note, title);

        }, { once: true });

      } else {

        img.hidden = true;

      }



      const title = document.createElement("strong");

      title.textContent = `Frame ${frame.frame_index ?? "—"} · ${formatTime(frame.timestamp_seconds)}`;



      card.append(img, title);



      if (frame.caption || frame.scene_context) {

  const description = document.createElement("p");

  const caption = frame.caption || frame.scene_context;



  // Display the actual description, not the model's metadata.

  const descriptionText =

    typeof caption === "object" && !Array.isArray(caption)

      ? caption.description ||

        caption.summary ||

        caption.caption ||

        caption.text ||

        ""

      : typeof caption === "string"

        ? caption

        : "";



  description.textContent =

    descriptionText || "No scene description available.";



  card.appendChild(description);

}



      const detections = Array.isArray(frame.detections) ? frame.detections : [];

      const detectionText = document.createElement("p");

      detectionText.className = "record-meta";

      detectionText.textContent = detections.length

        ? `${detections.length} object detection${detections.length === 1 ? "" : "s"}`

        : "No objects detected in this frame.";

      card.appendChild(detectionText);



      if (detections.length) {

        const list = document.createElement("ul");

        list.className = "limitation-list";

        detections.forEach(detection => {

          const item = document.createElement("li");

          const label = detection.label || detection.class_name || "Unidentified object";

          const confidence = Number(detection.confidence);

          item.textContent = Number.isFinite(confidence)

            ? `${label} (${(confidence * 100).toFixed(0)}% confidence)`

            : label;

          list.appendChild(item);

        });

        card.appendChild(list);

      }



      frameGrid.appendChild(card);

    });



    frameSection.appendChild(frameGrid);



    if (Array.isArray(data.limitations) && data.limitations.length) {

      const section = addSection("Review notes");

      const list = document.createElement("ul");

      list.className = "limitation-list";

      data.limitations.forEach(note => {

        const item = document.createElement("li");

        item.textContent = humanize(note);

        list.appendChild(item);

      });

      section.appendChild(list);

    }

  }



  async function handleVideoAnalysis() {

    const file = $("#video-file")?.files?.[0]; const button = $("#video-submit"); const status = $("#video-status"); const resultState = $("#video-result-state");

    if (!file) { setStatus(status, "Choose a video file before starting analysis.", "error"); return; }

    const allowed = [".mp4", ".avi", ".mov", ".mkv", ".webm"];

    if (!allowed.some((ext) => file.name.toLowerCase().endsWith(ext))) { setStatus(status, "Unsupported video format.", "error"); return; }

    if (!file.size || file.size > 250 * 1024 * 1024) { setStatus(status, "Video must be non-empty and no larger than 250 MB.", "error"); return; }

    const interval = Number($("#video-interval")?.value || 1); const maxFrames = Number($("#video-max-frames")?.value || 120); const confidence = Number($("#video-confidence")?.value || 0.35);

    if (!(interval > 0) || !Number.isInteger(maxFrames) || maxFrames < 1 || maxFrames > 120) { setStatus(status, "Use a positive sampling interval and a maximum frame count from 1 to 120.", "error"); return; }

    button.disabled = true; button.classList.add("loading"); if (resultState) resultState.textContent = "Analysis in progress"; setStatus(status, "Registering evidence and preparing video analysis…"); renderEmpty($("#video-results"), "Video analysis may take several minutes depending on the selected frame count.");

    try {

      const { caseId, evidenceId } = await registerEvidenceIfSelected("video", file, "video");

      setStatus(status, `Analyzing sampled frames (maximum ${maxFrames})…`);

      const form = new FormData(); form.append("video", file); form.append("confidence_threshold", String(confidence)); form.append("sample_interval_seconds", String(interval)); form.append("max_frames", String(maxFrames));

      const data = await apiRequest("/api/video/analyze", { method: "POST", body: form });

      state.currentResults.video = data;renderVideoResult(data);



      await saveAnalysisIfSelected(caseId,evidenceId,"video_analysis",data);

      if (resultState) resultState.textContent = "Analysis completed";

      setStatus(status, caseId ? "Video analysis completed. Evidence was registered with the selected investigation." : "Video analysis completed.", "success");

      if (caseId) { await loadCases(); if (state.activeView === "investigations") await loadInvestigations(); if (state.activeView === "reports") await loadReports(); }

    } catch (error) { if (resultState) resultState.textContent = "Analysis failed"; setStatus(status, `Video analysis failed: ${error.message}`, "error"); renderEmpty($("#video-results"), "No successful video analysis result is available."); }

    finally { button.disabled = false; button.classList.remove("loading"); }

  }



  function initialize() {

    setupNavigation();



    setupFilePreview(

      "image-file",

      "image-preview",

      "image-preview-empty",

      "image-preview-meta",

      [".jpg", ".jpeg", ".png", ".webp"]

    );



    setupFilePreview(

      "audio-file",

      "audio-preview",

      "audio-preview-empty",

      "audio-preview-meta",

      [".mp3", ".m4a", ".wav", ".ogg", ".flac", ".webm"]

    );



    setupFilePreview(

      "video-file",

      "video-preview",

      "video-preview-empty",

      "video-preview-meta",

      [".mp4", ".avi", ".mov", ".mkv", ".webm"]

    );



    setupAudioControls();

    setupVideoControls();

    setupForms();



    renderEmpty($("#image-results"), "Run an image analysis to see results here.");

    renderEmpty($("#audio-results"), "Run an audio analysis to see results here.");

    renderEmpty($("#video-results"), "Run a video analysis to see results here.");



    navigateTo("image");

    loadCases();

  }



  initialize();

});
