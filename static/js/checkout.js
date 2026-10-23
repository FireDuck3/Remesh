/* Checkout: Nova Poshta city and warehouse pickers. Loaded only when the autocomplete is enabled.

   The inputs search through htmx (hx-get in the template). Here we
   - give /delivery/ the parameter names it expects (q, city_ref),
   - turn a click on a suggestion into the visible name + hidden ref fields,
   - throw away a ref as soon as the buyer edits the text it belonged to.
   Without this script (or without htmx) the fields still work as plain text inputs. */
(function () {
  "use strict";

  var cityName = document.getElementById("id_np_city_name");
  var cityRef = document.getElementById("id_np_city_ref");
  var warehouseName = document.getElementById("id_np_warehouse_name");
  var warehouseRef = document.getElementById("id_np_warehouse_ref");
  var cityResults = document.getElementById("np-city-results");
  var warehouseResults = document.getElementById("np-warehouse-results");
  if (!cityName || !cityRef || !warehouseName || !warehouseRef || !cityResults || !warehouseResults) {
    return;
  }

  function loadWarehouses(cityRefValue) {
    if (!window.htmx) {
      return;
    }
    window.htmx.ajax("GET", warehouseName.getAttribute("hx-get"), {
      target: "#np-warehouse-results",
      swap: "innerHTML",
      values: { city_ref: cityRefValue, q: "" },
    });
  }

  // The endpoints read q and city_ref; the inputs themselves are named after the form fields.
  document.body.addEventListener("htmx:configRequest", function (event) {
    var parameters = event.detail.parameters;
    if (event.detail.elt === cityName) {
      parameters.q = cityName.value;
    } else if (event.detail.elt === warehouseName) {
      parameters.q = warehouseName.value;
      parameters.city_ref = cityRef.value;
    }
  });

  cityResults.addEventListener("click", function (event) {
    var option = event.target.closest(".np-option");
    if (!option) {
      return;
    }
    cityName.value = option.dataset.name;
    cityRef.value = option.dataset.ref;
    warehouseName.value = "";
    warehouseRef.value = "";
    cityResults.innerHTML = "";
    warehouseResults.innerHTML = "";
    loadWarehouses(option.dataset.ref);
  });

  warehouseResults.addEventListener("click", function (event) {
    var option = event.target.closest(".np-option");
    if (!option) {
      return;
    }
    warehouseName.value = option.dataset.name;
    warehouseRef.value = option.dataset.ref;
    warehouseResults.innerHTML = "";
  });

  // Typing after picking: the text no longer matches the ref, so the ref must go. A different city also
  // invalidates the warehouse that was picked in the old one: its ref, its visible name (otherwise the
  // buyer would still see, and submit, a warehouse of the wrong city) and the list of that city's warehouses.
  cityName.addEventListener("input", function () {
    cityRef.value = "";
    warehouseName.value = "";
    warehouseRef.value = "";
    warehouseResults.innerHTML = "";
  });

  warehouseName.addEventListener("input", function () {
    warehouseRef.value = "";
  });
})();
