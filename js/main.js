class AppState {
  constructor(url_params) {
    this._url_params = url_params;
    this._url_params_hooks= [];
  }

  update_url(new_parts) {
    this._url_params = {...this.url_params, ...new_parts};
    const url = this._url_params;
    this._url_params_hooks((x) => x(url));
  }

  replace_url(new_url) {
    this._url_params = {};
    this.update_url(new_url);
  }

  register_hook(hook) {
    this._url_params_hooks.push(hook);
  }
}

let _state = null;
function init_state(url_params) {
  if (_state !== null) {
    throw new Error('State is already initialized!');
  }
  _state = new AppState(url_params);
  return _state
}

function changeState(index) {
  var url = new URL(window.location.href);
  old_parameter = url.searchParams.get("oi");
  if (old_parameter !== index) {
    return;
  }
  if (index == null) {
    url.searchParams.delete("oi");
  } else {
    url.searchParams.set("oi", index);
  }
  if (window.history.replaceState) {
    window.history.replaceState(window.history.state, "", url.href);
  }
}
function replace_image_size_inside(element, source, replacement) {
  if (element == null) {
    return;
  }
  var images = element.getElementsByTagName("img");
  for (var i = 0; i < images.length; i++) {
    var image = images[i];
    var repl = image.src.replace("size=" + source, "size=" + replacement);
    if (repl != image.src) {
      image.src = repl;
    }
    if (replacement == "original") {
      image.loading = "eager";
    }
  }
}
function this_is_overlay_element(element) {
  replace_image_size_inside(element, "preview", "original");
  var next = element.nextElementSibling;
  if (next != null) {
    replace_image_size_inside(next, "preview", "original");
    next = next.nextElementSibling;
  }
  var prev = element.previousElementSibling;
  if (prev != null) {
    replace_image_size_inside(prev, "preview", "original");
    prev = prev.previousElementSibling;
  }
  if (next != null) {
    replace_image_size_inside(next, "original", "preview");
  }
  if (prev != null) {
    replace_image_size_inside(prev, "original", "preview");
  }
}
function overlay(element, index) {
  this_is_overlay_element(element.parentElement);
  element.parentElement.classList.add("overlay");
  changeState(index);
}
function overlay_close(element) {
  var root = element.parentElement.parentElement;
  replace_image_size_inside(root, "original", "preview");
  replace_image_size_inside(root.previousElementSibling, "original", "preview");
  replace_image_size_inside(root.nextElementSibling, "original", "preview");
  root.classList.remove("overlay");
  changeState(null);
}
function overlay_prev(element, index) {
  this_is_overlay_element(
    element.parentElement.parentElement.previousElementSibling
  );
  element.parentElement.parentElement.previousElementSibling.classList.add(
    "overlay"
  );
  element.parentElement.parentElement.classList.remove("overlay");
  changeState(index - 1);
}
function overlay_next(element, index) {
  this_is_overlay_element(
    element.parentElement.parentElement.nextElementSibling
  );
  element.parentElement.parentElement.nextElementSibling.classList.add(
    "overlay"
  );
  element.parentElement.parentElement.classList.remove("overlay");
  changeState(index + 1);
}

function update_boundary(nw, se) {
  var input = document.getElementById("fbnd");
  input.value = JSON.stringify({
    tl: {
      latitude: nw.lat,
      longitude: nw.lng,
    },
    br: {
      latitude: se.lat,
      longitude: se.lng,
    },
  });
}

class PhotoMap {
  constructor (div_id, bounds, location_url_json) {
    this.map = L.map("map").setView([51.505, -0.09], 13);
    this.markers = {};
    this.last_update_timestamp = 0;
    this.location_url_json = location_url_json;
    const that = this;
    const update_markers = (e) => {that.update_markers(false)};
    this.map.on("load", update_markers);
    this.map.on("zoomend", update_markers);
    this.map.on("moveend", update_markers);
    this.map.on("zoom", update_markers);
    this.map.on("move", update_markers);
    this.map.on("resize", update_markers);

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(this.map);
    if (bounds !== undefined && bounds !== null) {
      this.map.fitBounds(bounds);
    }
  }

  update_url(update) {
    this.location_url_json = {...this.location_url_json, ...update};
  }

  update_markers(change_view=false) {
    // TODO: wrapped maps: shift from 0 + wrap around

    var bounds = this.map.getBounds();
    var nw = bounds.getNorthWest();
    var se = bounds.getSouthEast();
    update_boundary(nw, se);
    var sz = this.map.getSize();
    var cluster_pixel_size = 10;
    var timestamp = new Date().getTime();
    fetch("/api/location_clusters", {
      method: "POST",
      body: JSON.stringify({
        tl: {
          latitude: nw.lat,
          longitude: nw.lng,
        },
        br: {
          latitude: se.lat,
          longitude: se.lng,
        },
        res: {
          latitude: sz.y / cluster_pixel_size,
          longitude: sz.x / cluster_pixel_size,
        },
        of: 0.5,
        url: this.location_url_json,
      }),
      headers: {
        "Content-type": "application/json; charset=UTF-8",
      },
    })
      .then((response) => response.json())
      .then((clusters) => {
        if (timestamp < this.last_update_timestamp) {
          return;
        }
        if (change_view && clusters.length > 0) {
          const lats = clusters.map((x) => x.position.latitude);
          const longs = clusters.map((x) => x.position.longitude);
          var bounds = [[Math.max(...lats), Math.max(...longs)], [Math.min(...lats), Math.min(...longs)]];
          this.map.fitBounds(bounds);
          bounds = this.map.getBounds();
          var nw = bounds.getNorthWest();
          var se = bounds.getSouthEast();
          update_boundary(nw, se);
        }
        this.last_update_timestamp = timestamp;
        var new_markers = {};
        for (var i = 0; i < clusters.length; i++) {
          var cluster = clusters[i];
          var existing = this.markers[cluster.example_path_md5];
          if (existing !== undefined) {
            new_markers[cluster.example_path_md5] = existing;
            delete this.markers[cluster.example_path_md5];
            continue;
          }
          var marker = L.marker([
            cluster.position.latitude,
            cluster.position.longitude,
          ]).addTo(this.map);
          marker.bindPopup(
            [
              cluster.example_classification,
              "@ ",
              cluster.address_name,
              ", ",
              cluster.address_country,
              " (",
              cluster.size,
              ")<br/><img src='/img?hsh=",
              cluster.example_path_md5,
              "&size=preview' class='popup'>",
            ].join("")
          );
          new_markers[cluster.example_path_md5] = marker;
        }
        Object.values(this.markers).forEach((m) => m.remove());
        Object.keys(this.markers).forEach((m) => delete this.markers[m]);
        Object.entries(new_markers).forEach(
          (m) => (this.markers[m[0]] = m[1])
        );
      });
  }
}

function fetch_directories(url_data) {
  const url = `/internal/directories.html`;
  fetch(url, {
    method: "POST",
    body: JSON.stringify(url_data),
    headers: {
      "Content-type": "application/json; charset=UTF-8",
    },
  })
    .then((response) => response.text())
    .then((text) => {
      const gallery = document.getElementById("Directories");
      gallery.innerHTML = text;
    })
}
function update_dir(data) {
  url = {"directory": data};
  fetch_directories(url);
  fetch_gallery(url, 0, null);
}

function fetch_gallery(url_data, page, oi) {
  var url = `/internal/gallery.html?oi=${oi}`;
  if (oi === undefined || oi === null) {
    url = `/internal/gallery.html`;
  }
  fetch(url, {
    method: "POST",
    body: JSON.stringify(url_data),
    headers: {
      "Content-type": "application/json; charset=UTF-8",
    },
  })
    .then((response) => response.text())
    .then((text) => {
      const gallery = document.getElementById("GalleryImages");
      gallery.innerHTML = text;
      const prev = gallery.getElementsByClassName("prev-url");
      for (var i = 0; i < prev.length; i++) {
        p = prev[i];
        p.onclick=(e) => {
          const u = {...url_data, page: page - 1};
          fetch_gallery(u, page - 1, null); // TODO: fix oi parameter
        };
      }
      const next = gallery.getElementsByClassName("next-url");
      for (var i = 0; i < next.length; i++) {
        p = next[i];
        p.onclick=(e) => {
          const u = {...url_data, page: page + 1};
          fetch_gallery(u, page + 1, null); // TODO: fix oi parameter
        };
      }
    });
}

function update_dates(chart, location_url_json) {
  fetch("/api/date_clusters", {
    method: "POST",
    body: JSON.stringify({
      url: location_url_json,
      buckets: 100,
    }),
    headers: {
      "Content-type": "application/json; charset=UTF-8",
    },
  })
    .then((response) => response.json())
    .then((clusters) => {
      dates = clusters.map((c) => {
        return { x: c.avg_timestamp * 1000, y: c.total };
      });
      chart.data.datasets[0].data = dates;
      chart.update();
    });
}
function init_dates(location_url_json, map) {
  var state = {
    clickTimeStart: null,
    location_url_json: location_url_json,
  };
  const ctx = document.getElementById("DateChart");
  const chart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        {
          label: "# of Images",
          data: [],
          borderWidth: 1,
          showLine: false,
        },
      ],
    },
    options: {
      events: ["mousedown", "mouseup"],
      parsing: false,
      scales: {
        y: {
          beginAtZero: true,
        },
        x: {
          type: "time",
          time: {
            displayFormats: {
              quarter: "MMM YYYY",
            },
          },
        },
      },
    },
    plugins: [
      {
        id: "Events",
        beforeEvent(chart, args, pluginOptions) {
          const event = args.event;
          const canvasPosition = Chart.helpers.getRelativePosition(
            event,
            chart
          );
          const dataX = chart.scales.x.getValueForPixel(canvasPosition.x);
          const dataY = chart.scales.y.getValueForPixel(canvasPosition.y);
          console.log(event.type, dataX, dataY, state);
          if (event.type === "mousedown") {
            state.clickTimeStart = dataX;
          } else if (event.type === "mouseup") {
            const x = [state.clickTimeStart / 1000.0, dataX / 1000.0]
            x.sort()
            const [f, t] = x;
            console.log(f, t);
            const u = {...state.location_url_json, tsfrom: f, tsto: t};
            fetch_gallery(u, 0, null);
            update_dates(chart, u);
            fetch_directories(u);
            map.update_url({tsfrom: f, tsto: t});
            map.update_markers(true);
          }
        },
      },
    ],
  });
  update_dates(chart, location_url_json);
  return chart
}
