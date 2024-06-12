function changeState(index) {
  var url = new URL(window.location.href);
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
  var images = element.getElementsByTagName('img');
  for (var i = 0; i < images.length; i ++) {
    var image = images[i];
    var repl = image.src.replace('size=' + source, 'size=' + replacement);
    if (repl != image.src) {
        image.src = repl;
    }
    if (replacement == 'original') {
      image.loading = 'eager';
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
  element.parentElement.classList.add('overlay');
  changeState(index);
}
function overlay_close(element) {
  var root = element.parentElement.parentElement;
  replace_image_size_inside(root, 'original', 'preview');
  replace_image_size_inside(root.previousElementSibling, 'original', 'preview');
  replace_image_size_inside(root.nextElementSibling, 'original', 'preview');
  root.classList.remove('overlay');
  changeState(null);
}
function overlay_prev(element, index) {
  this_is_overlay_element(element.parentElement.parentElement.previousElementSibling);
  element.parentElement.parentElement.previousElementSibling.classList.add('overlay');
  element.parentElement.parentElement.classList.remove('overlay');
  changeState(index - 1);
}
function overlay_next(element, index) {
  this_is_overlay_element(element.parentElement.parentElement.nextElementSibling);
  element.parentElement.parentElement.nextElementSibling.classList.add('overlay');
  element.parentElement.parentElement.classList.remove('overlay');
  changeState(index + 1);
}

function update_boundary(nw, se) {
  var input = document.getElementById('fbnd');
  input.value = JSON.stringify({
    "tl": {
      "latitude": nw.lat,
      "longitude": nw.lng,
    },
    "br": {
      "latitude": se.lat,
      "longitude": se.lng,
    },
  });
}
function update_markers(map, state) {
    function inner(e) {
        // TODO: wrapped maps: shift from 0 + wrap around
        var bounds = map.getBounds();
        var nw = bounds.getNorthWest();
        var se = bounds.getSouthEast();
        update_boundary(nw, se);
        var sz = map.getSize();
        var cluster_pixel_size = 10;
        var timestamp = (new Date()).getTime();
        fetch("/api/location_clusters", {
          method: "POST",
          body: JSON.stringify({
            "tl": {
              "latitude": nw.lat,
              "longitude": nw.lng,
            },
            "br": {
              "latitude": se.lat,
              "longitude": se.lng,
            },
            "res": {
              "latitude": sz.y / cluster_pixel_size,
              "longitude": sz.x / cluster_pixel_size,
            },
            "of": 0.5,
            "url": state.location_url_json,
          }),
          headers: {
            "Content-type": "application/json; charset=UTF-8"
          }
        })
          .then((response) => response.json())
          .then((clusters) => {
            if (timestamp < state.last_update_timestamp) {
              return;
            }
            state.last_update_timestamp = timestamp;
            var new_markers = {};
            for (var i = 0; i < clusters.length; i++) {
                var cluster = clusters[i];
                var existing = state.markers[cluster.example_path_md5];
                if (existing !== undefined) {
                  new_markers[cluster.example_path_md5] = existing;
                  delete state.markers[cluster.example_path_md5];
                  continue;
                }
                var marker = L.marker([cluster.position.latitude, cluster.position.longitude]).addTo(map);
                marker.bindPopup([
                    cluster.example_classification,
                    "@ ",
                    cluster.address_name,
                    ", ",
                    cluster.address_country,
                    " (",
                    cluster.size,
                    ")<br/><img src='/img?hsh=",
                    cluster.example_path_md5,
                    "&size=preview' class='popup'>"
                ].join(''));
                new_markers[cluster.example_path_md5] = marker;
            }
            Object.values(state.markers).forEach((m) => m.remove());
            Object.keys(state.markers).forEach((m) => delete state.markers[m]);
            Object.entries(new_markers).forEach((m) => state.markers[m[0]] = m[1]);
          });
    };
    return inner

}

function init_map(bounds, location_url_json) {
  var map = L.map('map').setView([51.505, -0.09], 13);
  var state = {
    "markers": {},
    "last_update_timestamp": 0,
    "location_url_json": location_url_json,
  };
  map.on('load', update_markers(map, state));
  map.on('zoomend', update_markers(map, state));
  map.on('moveend', update_markers(map, state));
  map.on('zoom', update_markers(map, state));
  map.on('move', update_markers(map, state));
  map.on('resize', update_markers(map, state));

  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);
  if (bounds !== undefined && bounds !== null) {
      map.fitBounds(bounds);
  }
}

function fetch_gallery(url_data, oi) {
  var url = `/internal/gallery.html?oi=${oi}`;
  if (oi === undefined || oi === null) {
    url = `/internal/gallery.html`;
  }
  fetch(url, {
    method: "POST",
    body: JSON.stringify(url_data),
    headers: {
      "Content-type": "application/json; charset=UTF-8"
    }
  })
    .then((response) => response.text())
    .then((text) => {
        const gallery = document.getElementById("GalleryImages");
        gallery.innerHTML = text;
    })
}

function init_dates(location_url_json) {
  fetch("/api/date_clusters", {
    method: "POST",
    body: JSON.stringify({
      "url": location_url_json,
      "buckets": 100,
    }),
    headers: {
      "Content-type": "application/json; charset=UTF-8"
    }
  })
    .then((response) => response.json())
    .then((clusters) => {
  const ctx = document.getElementById('DateChart');
  dates = clusters.map((c) => {return {x: c.avg_timestamp * 1000, y: c.total}})
  new Chart(ctx, {
    type: 'line',
    data: {
      datasets: [{
        label: '# of Images',
        data: dates,
        borderWidth: 1,
        showLine: false
      }]
    },
    options: {
      events: ["mousedown", "mouseup", "click", "keydown", "keyup"],
      parsing: false,
      scales: {
        y: {
          beginAtZero: true
        },
        x: {
                type: 'time',
                time: {
                    displayFormats: {
                        quarter: 'MMM YYYY'
                    }
                }
            }

      }
    },
    plugins: [{
      id: 'Events',
      beforeEvent(chart, args, pluginOptions) {
        const event = args.event;
        const canvasPosition = Chart.helpers.getRelativePosition(event, chart);
        const dataX = chart.scales.x.getValueForPixel(canvasPosition.x);
        const dataY = chart.scales.y.getValueForPixel(canvasPosition.y);
        console.log(event);
        console.log(dataX, dataY);
        if (event.type === 'mouseout') {
          // process the event
        }
      }
    }]
  });
  })
}
