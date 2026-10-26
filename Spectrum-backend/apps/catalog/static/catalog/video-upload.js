/*
 * Event video field: the upload starts as soon as a file is chosen, straight
 * to storage (presigned S3 PUT, or the local endpoint), with a progress bar in
 * the row. The row's hidden input then holds the upload's token, and Save
 * sends only that. Save waits while any video is still uploading.
 */
(function () {
  "use strict";

  var VIDEO_EXT = /\.(mp4|mov|m4v|webm)$/i;
  var active = 0;

  function csrf() {
    var input = document.querySelector("input[name=csrfmiddlewaretoken]");
    if (input) return input.value;
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
  }

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

  function errorOf(xhr) {
    if (xhr.status === 413) return "too large for the server (nginx client_max_body_size)";
    if (xhr.status === 502 || xhr.status === 504) return "the server timed out (" + xhr.status + ")";
    try { return JSON.parse(xhr.responseText).error || "upload failed (" + xhr.status + ")"; }
    catch (e) { return "upload failed (" + xhr.status + ")"; }
  }

  function prepare(url, file) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({ name: file.name, size: file.size, type: file.type }),
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) throw new Error(data.error || response.statusText);
        return data;
      });
    });
  }

  function Field(root) {
    this.root = root;
    this.input = root.querySelector(".video-upload-input");
    this.token = root.querySelector(".video-upload-token");
    this.progress = root.querySelector(".video-upload-progress");
    this.bar = root.querySelector(".video-upload-bar span");
    this.line = root.querySelector(".video-upload-line");
    this.seq = 0;
    this.xhr = null;
  }

  Field.of = function (root) {
    if (!root._videoField) root._videoField = new Field(root);
    return root._videoField;
  };

  Field.prototype.show = function (state, width, text) {
    this.progress.hidden = false;
    this.root.classList.toggle("is-done", state === "done");
    this.root.classList.toggle("is-failed", state === "failed");
    this.bar.style.width = width + "%";
    this.line.textContent = text;
  };

  Field.prototype.start = function (file) {
    var self = this;
    var seq = ++this.seq;
    if (this.xhr) this.xhr.abort();
    this.token.value = "";
    if (!file) { this.progress.hidden = true; return; }
    var max = parseInt(this.root.dataset.maxBytes, 10) || 0;
    if (!VIDEO_EXT.test(file.name)) return this.fail(file, "not a video — use MP4, MOV or WebM");
    if (max && file.size > max) return this.fail(file, "larger than " + formatBytes(max));

    active++;
    var finished = false;
    var finish = function () { if (!finished) { finished = true; active--; } };
    this.show("", 0, "Preparing " + file.name + "…");
    prepare(this.root.dataset.prepareUrl, file)
      .then(function (entry) {
        if (seq !== self.seq) return;
        return self.send(file, entry).then(function () {
          if (seq !== self.seq) return;
          self.token.value = entry.token;
          self.show("done", 100, "Uploaded " + file.name + " · " + formatBytes(file.size) + " — press Save to keep it");
        });
      })
      .catch(function (error) {
        if (seq === self.seq && !error.aborted) self.fail(file, error.message);
      })
      .then(finish);
  };

  Field.prototype.send = function (file, entry) {
    var self = this;
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      self.xhr = xhr;
      var started = Date.now();
      var body;
      xhr.open(entry.method, entry.uploadUrl);
      if (entry.method === "PUT") {
        Object.keys(entry.headers || {}).forEach(function (key) { xhr.setRequestHeader(key, entry.headers[key]); });
        body = file;
      } else {
        xhr.setRequestHeader("X-CSRFToken", csrf());
        body = new FormData();
        body.append("token", entry.token);
        body.append("file", file);
      }
      xhr.upload.onprogress = function (event) {
        if (!event.lengthComputable) return;
        // The form's own bytes ride along with the file; count the file only.
        var sent = Math.min(file.size, (event.loaded / event.total) * file.size);
        var seconds = (Date.now() - started) / 1000;
        var parts = ["Uploading " + file.name, formatBytes(sent) + " / " + formatBytes(file.size)];
        if (seconds > 3 && sent > 0) {
          var speed = sent / seconds;
          parts.push(formatBytes(speed) + "/s", formatTime((file.size - sent) / speed));
        }
        self.show("", Math.floor((sent / file.size) * 100), parts.join(" · "));
      };
      xhr.upload.onload = function () { self.show("", 100, "Upload complete — storing " + file.name + "…"); };
      xhr.onload = function () {
        self.xhr = null;
        if (xhr.status >= 200 && xhr.status < 300) return resolve();
        reject(new Error(errorOf(xhr)));
      };
      xhr.onerror = function () { self.xhr = null; reject(new Error("the connection dropped")); };
      xhr.onabort = function () { reject({ aborted: true }); };
      xhr.send(body);
    });
  };

  Field.prototype.fail = function (file, reason) {
    this.show("failed", 100, file.name + ": " + reason + ". Choose the file again to retry.");
    // Cleared so choosing the same file again starts a new upload.
    this.input.value = "";
  };

  // Delegated, so rows added with "Add another Event video" work too.
  document.addEventListener("change", function (event) {
    var input = event.target;
    if (!input.classList || !input.classList.contains("video-upload-input")) return;
    Field.of(input.closest(".video-upload")).start(input.files && input.files[0]);
  });

  document.addEventListener("submit", function (event) {
    if (!active) return;
    event.preventDefault();
    alert("A video is still uploading. Press Save again once its bar is complete.");
  }, true);

  window.addEventListener("beforeunload", function (event) {
    if (!active) return;
    event.preventDefault();
    event.returnValue = "";
  });

  // A form sent back with errors still holds finished uploads; say so.
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".video-upload").forEach(function (root) {
      var field = Field.of(root);
      if (field.token.value) field.show("done", 100, "Video uploaded — press Save to keep it");
    });
  });
})();
