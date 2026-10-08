/*
 * Spectrum admin bulk uploader. Drop files or folders, pick many, or paste.
 * Files go straight to storage (presigned S3 PUT, or the local endpoint), then are
 * committed in chunks. Only counts and failures are rendered, so 1,000 files stay light.
 */
(function () {
  "use strict";

  var CONCURRENCY = 4;
  var COMMIT_EVERY = 25;
  var PREPARE_CHUNK = 200;
  var RETRIES = 3;
  var IMAGE_EXT = /\.(jpe?g|png|webp|heic|heif|tiff?|bmp|gif)$/i;
  var uploaders = [];
  var lastActive = null;

  function csrf() {
    var input = document.querySelector("input[name=csrfmiddlewaretoken]");
    if (input) return input.value;
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
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

  function sleep(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }

  function naturalCompare(a, b) {
    return (a.relativePath || a.name).localeCompare(b.relativePath || b.name, undefined, { numeric: true, sensitivity: "base" });
  }

  function formatBytes(bytes) {
    if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  }

  function readEntries(entry) {
    return new Promise(function (resolve) {
      if (entry.isFile) {
        entry.file(function (file) { file.relativePath = entry.fullPath; resolve([file]); }, function () { resolve([]); });
        return;
      }
      if (!entry.isDirectory) return resolve([]);
      var reader = entry.createReader();
      var all = [];
      (function next() {
        reader.readEntries(function (entries) {
          if (!entries.length) {
            Promise.all(all.map(readEntries)).then(function (lists) { resolve([].concat.apply([], lists)); });
            return;
          }
          all = all.concat(Array.prototype.slice.call(entries));
          next();
        }, function () { resolve([]); });
      })();
    });
  }

  function filesFromDrop(dataTransfer) {
    var items = dataTransfer.items;
    if (items && items.length && items[0].webkitGetAsEntry) {
      var entries = [];
      for (var i = 0; i < items.length; i++) {
        var entry = items[i].webkitGetAsEntry && items[i].webkitGetAsEntry();
        if (entry) entries.push(entry);
      }
      return Promise.all(entries.map(readEntries)).then(function (lists) { return [].concat.apply([], lists); });
    }
    return Promise.resolve(Array.prototype.slice.call(dataTransfer.files || []));
  }

  function Uploader(root) {
    this.root = root;
    this.target = root.dataset.target;
    this.parentId = root.dataset.parent;
    this.prepareUrl = root.dataset.prepareUrl;
    this.gridUrl = root.dataset.gridUrl;
    this.maxBytes = parseInt(root.dataset.maxBytes, 10) || 40 * 1024 * 1024;
    this.batchId = null;
    this.nextIndex = 0;
    this.seq = 0;
    this.queue = [];
    this.toCommit = [];
    this.failed = [];
    this.active = 0;
    this.committing = Promise.resolve();
    this.polling = false;
    this.stats = { total: 0, uploaded: 0, committed: 0, bytesTotal: 0, bytesDone: 0 };

    this.drop = root.querySelector(".bulk-drop");
    this.input = root.querySelector(".bulk-input");
    this.progress = root.querySelector(".bulk-progress");
    this.bar = root.querySelector(".bulk-bar span");
    this.line = root.querySelector(".bulk-line");
    this.errors = root.querySelector(".bulk-errors");
    this.retryButton = root.querySelector(".bulk-retry");
    this.grid = root.querySelector(".bulk-grid");
    this.count = root.querySelector(".bulk-count");
    this.bind();
  }

  Uploader.prototype.bind = function () {
    var self = this;
    var activate = function () { lastActive = self; };
    this.root.addEventListener("mouseenter", activate);
    this.root.addEventListener("focusin", activate);
    this.drop.addEventListener("click", function (event) {
      activate();
      if (event.target.classList.contains("bulk-browse")) self.input.click();
      else self.drop.focus();
    });
    this.drop.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); self.input.click(); }
    });
    this.input.addEventListener("change", function () {
      self.add(Array.prototype.slice.call(self.input.files));
      self.input.value = "";
    });
    ["dragenter", "dragover"].forEach(function (type) {
      self.drop.addEventListener(type, function (event) {
        event.preventDefault();
        self.drop.classList.add("is-over");
      });
    });
    ["dragleave", "drop"].forEach(function (type) {
      self.drop.addEventListener(type, function () { self.drop.classList.remove("is-over"); });
    });
    this.drop.addEventListener("drop", function (event) {
      event.preventDefault();
      activate();
      filesFromDrop(event.dataTransfer).then(function (files) { self.add(files); });
    });
    this.retryButton.addEventListener("click", function () { self.retryFailed(); });
    this.bindSelection();
  };

  /* Tick boxes on the thumbnail grid (only rendered where the admin may
     delete): shift-click ticks a range, "Select all" ticks every shown photo,
     and "Delete selected" posts the ids and swaps in the grid it gets back.
     Listeners sit on the grid container, so they survive its refreshes. */
  Uploader.prototype.bindSelection = function () {
    var self = this;
    var lastBox = null;
    var boxes = function () { return Array.prototype.slice.call(self.grid.querySelectorAll(".bulk-select")); };
    this.grid.addEventListener("click", function (event) {
      var box = event.target;
      if (!box.classList || !box.classList.contains("bulk-select")) return;
      if (event.shiftKey && lastBox && lastBox !== box && self.grid.contains(lastBox)) {
        var all = boxes();
        var from = all.indexOf(lastBox), to = all.indexOf(box);
        all.slice(Math.min(from, to), Math.max(from, to) + 1).forEach(function (b) { b.checked = box.checked; });
      }
      lastBox = box;
      self.syncSelection();
    });
    this.grid.addEventListener("change", function (event) {
      if (!event.target.classList || !event.target.classList.contains("bulk-select-all")) return;
      boxes().forEach(function (b) { b.checked = event.target.checked; });
      self.syncSelection();
    });
    this.grid.addEventListener("click", function (event) {
      var button = event.target.closest && event.target.closest(".bulk-delete-selected");
      if (!button || button.disabled) return;
      var ids = boxes().filter(function (b) { return b.checked; }).map(function (b) { return b.value; });
      if (!ids.length) return;
      if (!confirm("Delete " + ids.length + " selected photo(s)? This cannot be undone.")) return;
      button.disabled = true;
      button.textContent = "Deleting…";
      fetch(button.closest(".bulk-selectbar").dataset.url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
        body: JSON.stringify({ target: self.target, parent: self.parentId, ids: ids }),
      })
        .then(function (response) {
          if (!response.ok) throw new Error(response.statusText || "Delete failed");
          return response.text();
        })
        .then(function (html) { self.showGrid(html); })
        .catch(function (error) {
          alert("Could not delete the photos: " + error.message);
          button.textContent = "Delete selected images";
          self.syncSelection();
        });
    });
  };

  Uploader.prototype.syncSelection = function () {
    var bar = this.grid.querySelector(".bulk-selectbar");
    if (!bar) return;
    var all = this.grid.querySelectorAll(".bulk-select");
    var ticked = this.grid.querySelectorAll(".bulk-select:checked").length;
    var master = bar.querySelector(".bulk-select-all");
    master.checked = all.length > 0 && ticked === all.length;
    master.indeterminate = ticked > 0 && ticked < all.length;
    bar.querySelector(".bulk-selected-count").textContent = ticked ? ticked + " selected" : "None selected";
    var button = bar.querySelector(".bulk-delete-selected");
    button.disabled = !ticked;
    button.textContent = ticked ? "Delete selected images (" + ticked + ")" : "Delete selected images";
  };

  Uploader.prototype.add = function (files) {
    var self = this;
    var accepted = [];
    files.forEach(function (file) {
      var isImage = (file.type && file.type.indexOf("image/") === 0) || IMAGE_EXT.test(file.name);
      if (!isImage) return;
      if (file.size > self.maxBytes) return self.fail({ file: file }, "larger than " + formatBytes(self.maxBytes));
      accepted.push(file);
    });
    if (!accepted.length) return this.render();
    accepted.sort(naturalCompare);
    var items = accepted.map(function (file) {
      self.stats.total += 1;
      self.stats.bytesTotal += file.size;
      return { file: file, clientId: Date.now().toString(36) + "-" + (self.seq++), index: self.nextIndex++, attempts: 0 };
    });
    this.progress.hidden = false;
    this.render();
    var chunks = [];
    for (var i = 0; i < items.length; i += PREPARE_CHUNK) chunks.push(items.slice(i, i + PREPARE_CHUNK));
    return chunks.reduce(function (promise, chunk) {
      return promise.then(function () { return self.prepare(chunk); }).then(function () { self.pump(); });
    }, Promise.resolve());
  };

  Uploader.prototype.prepare = function (items) {
    var self = this;
    return postJSON(this.prepareUrl, {
      target: this.target,
      parentId: this.parentId,
      batchId: this.batchId,
      files: items.map(function (item) {
        return { clientId: item.clientId, name: item.file.name, size: item.file.size, type: item.file.type };
      }),
    }).then(function (data) {
      self.batchId = data.batchId;
      var byId = {};
      data.files.forEach(function (entry) { byId[entry.clientId] = entry; });
      items.forEach(function (item) {
        var entry = byId[item.clientId];
        if (!entry || entry.error) return self.fail(item, entry ? entry.error : "rejected");
        item.entry = entry;
        self.queue.push(item);
      });
    }).catch(function (error) {
      items.forEach(function (item) { self.fail(item, error.message); });
    });
  };

  Uploader.prototype.send = function (item) {
    var self = this;
    var entry = item.entry;
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      var body;
      xhr.open(entry.method, entry.uploadUrl);
      if (entry.method === "PUT") {
        Object.keys(entry.headers || {}).forEach(function (key) { xhr.setRequestHeader(key, entry.headers[key]); });
        body = item.file;
      } else {
        xhr.setRequestHeader("X-CSRFToken", csrf());
        body = new FormData();
        body.append("token", entry.token);
        body.append("file", item.file);
      }
      var reported = 0;
      xhr.upload.onprogress = function (event) {
        if (!event.lengthComputable) return;
        self.stats.bytesDone += event.loaded - reported;
        reported = event.loaded;
        self.renderSoon();
      };
      xhr.onload = function () {
        self.stats.bytesDone += item.file.size - reported;
        if (xhr.status >= 200 && xhr.status < 300) return resolve();
        self.stats.bytesDone -= item.file.size;
        var error = new Error("upload failed (" + xhr.status + ")");
        error.status = xhr.status;
        reject(error);
      };
      xhr.onerror = function () {
        self.stats.bytesDone -= reported;
        reject(new Error("network error"));
      };
      xhr.send(body);
    });
  };

  Uploader.prototype.pump = function () {
    var self = this;
    while (this.active < CONCURRENCY && this.queue.length) {
      this.start(this.queue.shift());
    }
    if (!this.active && !this.queue.length) {
      this.flush(true).then(function () { self.poll(); });
    }
  };

  Uploader.prototype.start = function (item) {
    var self = this;
    this.active += 1;
    var attempt = function () {
      item.attempts += 1;
      return self.send(item).catch(function (error) {
        if (item.attempts >= RETRIES) throw error;
        var retry = sleep(1000 * Math.pow(3, item.attempts - 1));
        if (error.status === 403 && item.entry.method === "PUT") {
          // Presigned URL expired: ask for a fresh one.
          retry = retry.then(function () {
            return postJSON(self.prepareUrl, {
              target: self.target, parentId: self.parentId, batchId: self.batchId,
              files: [{ clientId: item.clientId, name: item.file.name, size: item.file.size, type: item.file.type }],
            }).then(function (data) { item.entry = data.files[0]; });
          });
        }
        return retry.then(attempt);
      });
    };
    attempt()
      .then(function () {
        self.stats.uploaded += 1;
        self.toCommit.push(item);
        if (self.toCommit.length >= COMMIT_EVERY) self.flush(false);
      })
      .catch(function (error) { self.fail(item, error.message); })
      .then(function () {
        self.active -= 1;
        self.render();
        self.pump();
      });
  };

  Uploader.prototype.flush = function (all) {
    var self = this;
    this.committing = this.committing.then(function () {
      var rounds = [];
      while (self.toCommit.length && (all || self.toCommit.length >= COMMIT_EVERY)) {
        rounds.push(self.toCommit.splice(0, 50));
      }
      return rounds.reduce(function (promise, batch) {
        return promise.then(function () { return self.commit(batch, 0); });
      }, Promise.resolve());
    });
    return this.committing;
  };

  Uploader.prototype.options = function () {
    var options = {};
    this.root.querySelectorAll(".bulk-option").forEach(function (select) { options[select.dataset.key] = select.value; });
    return options;
  };

  Uploader.prototype.commit = function (batch, tries) {
    var self = this;
    return postJSON(this.prepareUrl.replace(/prepare\/$/, this.batchId + "/commit/"), {
      files: batch.map(function (item) { return { token: item.entry.token, index: item.index, name: item.file.name }; }),
      options: this.options(),
    }).then(function (data) {
      self.stats.committed += data.created.length;
      var skipped = {};
      data.skipped.forEach(function (id) { skipped[id] = true; });
      var reasons = data.errors || {};
      batch.forEach(function (item) {
        if (skipped[item.clientId]) self.fail(item, reasons[item.clientId] || "not found after upload");
      });
      self.render();
    }).catch(function (error) {
      if (tries < 2) return sleep(2000).then(function () { return self.commit(batch, tries + 1); });
      batch.forEach(function (item) { self.fail(item, "could not save: " + error.message); });
    });
  };

  Uploader.prototype.poll = function () {
    var self = this;
    if (this.polling || !this.batchId || !this.stats.committed) return this.refreshGrid();
    this.polling = true;
    var statusUrl = this.prepareUrl.replace(/prepare\/$/, this.batchId + "/status/");
    var tick = function () {
      fetch(statusUrl, { credentials: "same-origin" })
        .then(function (response) { return response.json(); })
        .then(function (counts) {
          var waiting = counts.pending + counts.processing;
          self.processing = counts;
          self.render();
          if (waiting > 0) return setTimeout(tick, 2000);
          self.polling = false;
          self.processing = null;
          self.render(counts);
          self.refreshGrid();
        })
        .catch(function () { setTimeout(tick, 4000); });
    };
    tick();
  };

  Uploader.prototype.refreshGrid = function () {
    var self = this;
    var url = this.gridUrl + "?target=" + encodeURIComponent(this.target) + "&parent=" + encodeURIComponent(this.parentId);
    return fetch(url, { credentials: "same-origin" })
      .then(function (response) { return response.text(); })
      .then(function (html) { self.showGrid(html, true); });
  };

  /* Swaps in fresh grid HTML; `keepTicks` re-ticks photos still present, so a
     refresh while uploads finish processing doesn't drop a selection. */
  Uploader.prototype.showGrid = function (html, keepTicks) {
    var self = this;
    var ticked = keepTicks
      ? Array.prototype.map.call(this.grid.querySelectorAll(".bulk-select:checked"), function (b) { return b.value; })
      : [];
    this.grid.innerHTML = html;
    ticked.forEach(function (id) {
      var box = self.grid.querySelector('.bulk-select[value="' + id + '"]');
      if (box) box.checked = true;
    });
    this.syncSelection();
    var link = this.grid.querySelector(".bulk-manage a");
    var plain = this.grid.querySelector(".bulk-manage [data-total]");
    var empty = !link && !plain;
    if (this.count && plain) this.count.textContent = plain.dataset.total;
    if (this.count && link) {
      var match = link.textContent.match(/\((\d+)\)/);
      if (match) this.count.textContent = match[1];
    }
    if (this.count && empty) this.count.textContent = "0";
  };

  Uploader.prototype.fail = function (item, reason) {
    this.failed.push(item);
    var li = document.createElement("li");
    li.textContent = item.file.name + ": " + reason;
    this.errors.appendChild(li);
    this.retryButton.hidden = !this.failed.some(function (f) { return f.clientId; });
    this.progress.hidden = false;
  };

  Uploader.prototype.retryFailed = function () {
    var files = this.failed.filter(function (item) { return item.clientId; }).map(function (item) { return item.file; });
    this.failed = [];
    this.errors.innerHTML = "";
    this.retryButton.hidden = true;
    this.stats.total -= files.length;
    this.stats.bytesTotal -= files.reduce(function (sum, file) { return sum + file.size; }, 0);
    this.add(files);
  };

  Uploader.prototype.renderSoon = function () {
    var self = this;
    if (this.frame) return;
    this.frame = requestAnimationFrame(function () { self.frame = null; self.render(); });
  };

  Uploader.prototype.render = function (finalCounts) {
    var stats = this.stats;
    var percent = stats.bytesTotal ? Math.min(100, Math.round((stats.bytesDone / stats.bytesTotal) * 100)) : 0;
    this.bar.style.width = percent + "%";
    var parts;
    if (this.processing) {
      var done = this.processing.ready + this.processing.failed;
      parts = ["Uploaded " + stats.committed + ". Making web versions: " + done + " of " + this.processing.total + "…"];
    } else if (finalCounts) {
      parts = ["Done. " + finalCounts.ready + " ready" + (finalCounts.failed ? ", " + finalCounts.failed + " could not be read" : "") + "."];
    } else {
      parts = ["Uploading " + stats.uploaded + " of " + stats.total, formatBytes(stats.bytesDone) + " / " + formatBytes(stats.bytesTotal)];
    }
    if (this.failed.length) parts.push(this.failed.length + " failed");
    this.line.textContent = parts.join(" · ");
  };

  Uploader.prototype.busy = function () {
    return this.active > 0 || this.queue.length > 0 || this.toCommit.length > 0;
  };

  function init() {
    document.querySelectorAll(".bulk-upload").forEach(function (root) { uploaders.push(new Uploader(root)); });
    if (!uploaders.length) return;
    lastActive = uploaders[0];

    // Stop the browser from opening a file dropped just outside the zone.
    ["dragover", "drop"].forEach(function (type) {
      window.addEventListener(type, function (event) {
        if (event.dataTransfer && Array.prototype.indexOf.call(event.dataTransfer.types || [], "Files") !== -1) event.preventDefault();
      });
    });

    document.addEventListener("paste", function (event) {
      var files = Array.prototype.slice.call((event.clipboardData && event.clipboardData.files) || []);
      if (!files.length || !lastActive) return;
      event.preventDefault();
      lastActive.add(files);
    });

    window.addEventListener("beforeunload", function (event) {
      if (uploaders.some(function (u) { return u.busy(); })) {
        event.preventDefault();
        event.returnValue = "";
      }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
