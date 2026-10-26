/*
 * Upload progress on Save, for admin forms that carry big files (event videos
 * run to gigabytes). When a file has been chosen, the form is sent with
 * XMLHttpRequest so the bytes sent can be shown; the page the server answers
 * with then replaces this one, as a normal submit would. Forms without a
 * chosen file submit as usual.
 */
(function () {
  "use strict";

  function formatBytes(bytes) {
    if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
    return (bytes / 1024 / 1024 / 1024).toFixed(2) + " GB";
  }

  function formatTime(seconds) {
    if (seconds < 60) return "under a minute left";
    var minutes = Math.round(seconds / 60);
    if (minutes < 60) return "about " + minutes + " min left";
    return "about " + Math.floor(minutes / 60) + " h " + (minutes % 60) + " min left";
  }

  /* Files the form will send. The bulk photo uploader's inputs have no name,
     so they are not part of the form and are left out. */
  function chosenFiles(form) {
    var files = [];
    form.querySelectorAll('input[type="file"][name]').forEach(function (input) {
      Array.prototype.forEach.call(input.files || [], function (file) { files.push(file); });
    });
    return files;
  }

  function Panel(files) {
    this.root = document.createElement("div");
    this.root.className = "save-progress";
    this.root.innerHTML =
      '<div class="save-progress-card" role="dialog" aria-modal="true" aria-live="polite">' +
      '<h2></h2><div class="save-progress-bar"><span></span></div><p class="save-progress-line"></p>' +
      '<p class="save-progress-note">Keep this tab open until it finishes.</p>' +
      '<button type="button" class="button save-progress-close" hidden>Close</button></div>';
    this.title = this.root.querySelector("h2");
    this.bar = this.root.querySelector(".save-progress-bar");
    this.fill = this.bar.querySelector("span");
    this.line = this.root.querySelector(".save-progress-line");
    this.note = this.root.querySelector(".save-progress-note");
    this.close = this.root.querySelector(".save-progress-close");
    this.title.textContent = files.length === 1 ? "Uploading " + files[0].name : "Uploading " + files.length + " files";
    this.line.textContent = "Starting…";
    var self = this;
    this.close.addEventListener("click", function () { self.root.remove(); });
    document.body.appendChild(this.root);
  }

  Panel.prototype.progress = function (loaded, total, seconds) {
    var percent = Math.floor((loaded / total) * 100);
    this.fill.style.width = percent + "%";
    var parts = [percent + "%", formatBytes(loaded) + " of " + formatBytes(total)];
    if (seconds > 3 && loaded > 0) {
      var speed = loaded / seconds;
      parts.push(formatBytes(speed) + "/s", formatTime((total - loaded) / speed));
    }
    this.line.textContent = parts.join(" · ");
  };

  Panel.prototype.saving = function () {
    this.title.textContent = "Upload complete — saving…";
    this.fill.style.width = "100%";
    this.bar.classList.add("is-busy");
    this.line.textContent = "The server is storing the file. A large video can take a minute or two.";
  };

  Panel.prototype.fail = function (message) {
    this.title.textContent = "Not saved";
    this.bar.classList.remove("is-busy");
    this.bar.classList.add("is-failed");
    this.line.textContent = message;
    this.note.textContent = "Your entries and chosen files are still on the page. Press Save to try again.";
    this.close.hidden = false;
  };

  function failure(status) {
    if (status === 413) return "The file is larger than the server accepts (nginx client_max_body_size).";
    if (status === 502 || status === 504) return "The server took too long to answer (" + status + "). Check the gunicorn and nginx timeouts.";
    if (status === 403) return "The session expired or the security token is stale. Reload the page and try again.";
    return "The server answered with an error (" + status + ").";
  }

  function send(form, submitter, files) {
    var data = new FormData(form);
    if (submitter && submitter.name) data.append(submitter.name, submitter.value);
    var panel = new Panel(files);
    var started = Date.now();
    var leaving = function (event) { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", leaving);

    var xhr = new XMLHttpRequest();
    xhr.open("POST", form.action || window.location.href);
    // A successful save then answers with JSON naming the next page (see
    // UploadProgressMixin), so its "saved" message is kept for that page.
    xhr.setRequestHeader("X-Upload-Progress", "1");
    xhr.upload.onprogress = function (event) {
      if (event.lengthComputable) panel.progress(event.loaded, event.total, (Date.now() - started) / 1000);
    };
    xhr.upload.onload = function () { panel.saving(); };
    xhr.onload = function () {
      window.removeEventListener("beforeunload", leaving);
      if (xhr.status < 200 || xhr.status >= 300) return panel.fail(failure(xhr.status));
      if ((xhr.getResponseHeader("Content-Type") || "").indexOf("application/json") === 0) {
        window.location.href = JSON.parse(xhr.responseText).redirect;
        return;
      }
      // The form again, with its errors: show it as the browser would have.
      if (xhr.responseURL) history.replaceState(null, "", xhr.responseURL);
      document.open();
      document.write(xhr.responseText);
      document.close();
    };
    xhr.onerror = function () {
      window.removeEventListener("beforeunload", leaving);
      panel.fail("The connection dropped before the upload finished.");
    };
    xhr.send(data);
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (event.defaultPrevented || form.method.toLowerCase() !== "post" || form.enctype !== "multipart/form-data") return;
    var files = chosenFiles(form);
    if (!files.length) return;
    event.preventDefault();
    send(form, event.submitter, files);
  });
})();
