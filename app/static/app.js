(function () {
  const input = document.querySelector("#file-input");
  const zone = document.querySelector("[data-dropzone]");
  const label = document.querySelector("[data-file-name]");

  if (!input || !zone || !label) return;

  function showName() {
    const file = input.files && input.files[0];
    if (!file) {
      label.textContent = "CSV or Excel · up to 16 MB";
      label.classList.remove("has-file");
      return;
    }
    label.textContent = file.name;
    label.classList.add("has-file");
  }

  input.addEventListener("change", showName);

  ["dragenter", "dragover"].forEach(function (name) {
    zone.addEventListener(name, function (event) {
      event.preventDefault();
      zone.classList.add("is-dragging");
    });
  });

  ["dragleave", "dragend"].forEach(function (name) {
    zone.addEventListener(name, function () {
      zone.classList.remove("is-dragging");
    });
  });

  zone.addEventListener("drop", function (event) {
    event.preventDefault();
    zone.classList.remove("is-dragging");
    if (!event.dataTransfer || !event.dataTransfer.files.length) return;
    input.files = event.dataTransfer.files;
    showName();
  });
})();
