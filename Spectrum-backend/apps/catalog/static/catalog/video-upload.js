/*
 * Event video field: the upload starts as soon as a file is chosen, straight
 * to storage (presigned S3 PUT, or the local endpoint), with a progress bar in
 * the row. The row's hidden input then holds the upload's token, and Save
 * sends only that. Save waits while any video is still uploading.
 *
 * Large videos on S3 go up in parts (method MULTIPART): a few at a time, each
 * retried on its own if the connection drops, then joined by the server.
 */
(function () {
  "use strict";

  var VIDEO_EXT = /\.(mp4|mov|m4v|webm)$/i;
  var PARALLEL_PARTS = 3;
  var PART_RETRIES = 4;
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

  function postJSON(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify(body),
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) throw new Error(data.error || response.statusText);
        return data;
      });
    });
  }

  function prepare(url, file) {
    return postJSON(url, { name: file.name, size: file.size, type: file.type });
  }

  function sleep(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }

  function Field(root) {
    this.root = root;
    this.input = root.querySelector(".video-upload-input");
    this.token = root.querySelector(".video-upload-token");
    this.progress = root.querySelector(".video-upload-progress");
    this.bar = root.querySelector(".video-upload-bar span");
    this.line = root.querySelector(".video-upload-line");
    this.seq = 0;
    this.xhrs = [];
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
    this.stop();
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

  /* Cancels whatever is in flight: a new file was chosen. */
  Field.prototype.stop = function () {
    this.xhrs.splice(0).forEach(function (xhr) { xhr.abort(); });
  };

  Field.prototype.track = function (xhr) {
    var xhrs = this.xhrs;
    xhrs.push(xhr);
    return function () { var i = xhrs.indexOf(xhr); if (i !== -1) xhrs.splice(i, 1); };
  };

  /* "Uploading x · 1.2 GB / 6.4 GB · 8.1 MB/s · about 11 min left" */
  Field.prototype.report = function (file, sent, started) {
    var seconds = (Date.now() - started) / 1000;
    var parts = ["Uploading " + file.name, formatBytes(sent) + " / " + formatBytes(file.size)];
    if (seconds > 3 && sent > 0) {
      var speed = sent / seconds;
      parts.push(formatBytes(speed) + "/s", formatTime((file.size - sent) / speed));
    }
    this.show("", Math.min(99, Math.floor((sent / file.size) * 100)), parts.join(" · "));
  };

  Field.prototype.send = function (file, entry) {
    if (entry.method === "MULTIPART") return this.sendParts(file, entry);
    var self = this;
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      var untrack = self.track(xhr);
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
        self.report(file, Math.min(file.size, (event.loaded / event.total) * file.size), started);
      };
      xhr.upload.onload = function () { self.show("", 100, "Upload complete — storing " + file.name + "…"); };
      xhr.onload = function () {
        untrack();
        if (xhr.status >= 200 && xhr.status < 300) return resolve();
        reject(new Error(errorOf(xhr)));
      };
      xhr.onerror = function () { untrack(); reject(new Error("the connection dropped")); };
      xhr.onabort = function () { untrack(); reject({ aborted: true }); };
      xhr.send(body);
    });
  };

  /* A large video on S3, in parts of entry.partSize: PARALLEL_PARTS at a time,
     each retried with a growing pause, part URLs fetched a batch at a time as
     they are needed. The server then joins them; on failure it is told to
     abort, so no half-upload is left taking up space. */
  Field.prototype.sendParts = function (file, entry) {
    var self = this;
    var size = entry.partSize;
    var total = Math.ceil(file.size / size);
    var sent = {};  // part number -> bytes of it sent so far
    var started = Date.now();
    var batches = {};  // batch index -> promise of {number: url}
    var next = 1;
    var stopped = false;
    var base = { token: entry.token, uploadId: entry.uploadId };

    function progress() {
      var bytes = 0;
      for (var n in sent) bytes += sent[n];
      self.report(file, bytes, started);
    }

    function urlFor(n, fresh) {
      var batch = Math.floor((n - 1) / 50);
      if (fresh || !batches[batch]) {
        var numbers = [];
        for (var i = batch * 50 + 1; i <= Math.min(total, batch * 50 + 50); i++) numbers.push(i);
        batches[batch] = postJSON(entry.partsUrl, Object.assign({ numbers: numbers }, base))
          .then(function (data) { return data.urls; });
      }
      return batches[batch].then(function (urls) { return urls[String(n)]; });
    }

    function putPart(n, url) {
      return new Promise(function (resolve, reject) {
        var xhr = new XMLHttpRequest();
        var untrack = self.track(xhr);
        xhr.open("PUT", url);
        xhr.upload.onprogress = function (event) { sent[n] = event.loaded; progress(); };
        xhr.onload = function () {
          untrack();
          if (xhr.status >= 200 && xhr.status < 300) { sent[n] = Math.min(size, file.size - (n - 1) * size); progress(); return resolve(); }
          reject(new Error("part " + n + " " + errorOf(xhr)));
        };
        xhr.onerror = function () { untrack(); reject(new Error("the connection dropped")); };
        xhr.onabort = function () { untrack(); reject({ aborted: true }); };
        xhr.send(file.slice((n - 1) * size, n * size));
      });
    }

    function attempt(n, tries) {
      // A retry fetches fresh URLs, in case the old one expired.
      return urlFor(n, tries > 0).then(function (url) { return putPart(n, url); }).catch(function (error) {
        if (error.aborted || stopped || tries + 1 >= PART_RETRIES) throw error;
        sent[n] = 0;
        progress();
        return sleep(2000 * Math.pow(2, tries)).then(function () { return attempt(n, tries + 1); });
      });
    }

    function worker() {
      if (stopped || next > total) return Promise.resolve();
      var n = next++;
      return attempt(n, 0).then(worker);
    }

    var workers = [];
    for (var i = 0; i < Math.min(PARALLEL_PARTS, total); i++) workers.push(worker());
    return Promise.all(workers)
      .then(function () {
        self.show("", 100, "Upload complete — joining the parts of " + file.name + "…");
        return postJSON(entry.completeUrl, Object.assign({ parts: total }, base));
      })
      .catch(function (error) {
        stopped = true;
        self.stop();
        postJSON(entry.abortUrl, base).catch(function () {});
        throw error;
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
