/*!
 * fastshell
 * Fiercely quick and opinionated front-ends
 * https://HosseinKarami.github.io/fastshell
 * @author Hossein Karami
 * @version 1.0.5
 * Copyright 2016. MIT licensed.
 */
(function (window, document, undefined) {

  'use strict';

  // Leaflet coords
  // y corresponds to northing
  // x corresponds to easting
  // var yx = L.latLng;

  // var xy = function(x, y) {
  //     if (L.Util.isArray(x)) {    // When doing xy([x, y]);
  //         return yx(x[1], x[0]);
  //     }
  //     return yx(y, x);  // When doing xy(x, y);
  // };

  // Polyfill for Object.assign()
  if (typeof Object.assign !== 'function') {
    (function () {
      Object.assign = function (target) {
        'use strict';
        if (target === undefined || target === null) {
          throw new TypeError('Cannot convert undefined or null to object');
        }

        var output = Object(target);
        for (var index = 1; index < arguments.length; index++) {
          var source = arguments[index];
          if (source !== undefined && source !== null) {
            for (var nextKey in source) {
              if (source.hasOwnProperty(nextKey)) {
                output[nextKey] = source[nextKey];
              }
            }
          }
        }
        return output;
      };
    })();
  }

  // [bottom, top], [left, right]

  var left = 900000.0,
    bottom = 899500.0,
    right = 7401000.0,
    top = 5500000.0;
  //var MAP_BOUNDS = [[left, bottom], [right, top]];
  var southwest = [bottom, left],
    northeast = [top, right],
    MAP_BOUNDS = [southwest, northeast];

  (function () {
    // dimensions of the image and the map
    var wProj = Math.abs(right-left), hProj = Math.abs(bottom-top);
    var mapRect = d3.select('#substrates-map').node().getBoundingClientRect(),
      mapW = mapRect.width,
      mapH = mapRect.height;

    var wScale = mapW / wProj,
      hScale = mapH / hProj;

    var minZoom = Math.ceil(Math.log2(Math.min(wScale, hScale)));

    var map = L.map('substrates-map', {
      minZoom: minZoom,
      center: [(bottom+top)/2, (right+left)*0.55],
      zoom: minZoom,
      crs: L.CRS.Simple,
      maxBounds: MAP_BOUNDS
    });

    map.createPane('substrates');
    map.getPane('substrates').style.zIndex = 500;

    var imageOverlays = {};

    function setSubstrate(item) {
      var url = 'assets/substrates/' + item.key + '.png';
      if (!(url in imageOverlays)) {
        imageOverlays[url] = L.imageOverlay(url, MAP_BOUNDS);
      }
      for (var otherUrl in imageOverlays) {
        map.removeLayer(imageOverlays[otherUrl]);
      }
      map.addLayer(imageOverlays[url], {'pane': 'substrates'});

      var colorbarUrl = 'assets/substrates/cbar_' + item.key + '.png';
      var cbarImg = d3.select('#substrates-colorbar')
        .selectAll('img')
        .data([colorbarUrl]);

      cbarImg
        .enter()
        .append('img');

      cbarImg.attr('src', function(d) { return d; });

      var cbarImg = d3.select('#substrates-colorbar')
        .selectAll('img')
        .data([colorbarUrl]);

      d3.select('#map-caption').text(item.label);
      d3.select('#map-unit').html(item.unit);

    }

    d3.json('assets/ne_bbox.geojson', function (err, neData) {
      map.createPane('bg');
      map.getPane('bg').style.zIndex = 300;
      map.createPane('outline');
      map.getPane('outline').style.zIndex = 1000;

      var bg = L.geoJson(
        neData,
        {
          'fillColor': '#cccccc',
          'weight': 0,
          'fillOpacity': 1,
          'pane': 'bg'
        });
      bg.addTo(map);

      var outline = L.geoJson(
        neData,
        {
          'color': '#333333',
          'weight': 1,
          'opacity': 1,
          'fillOpacity': 0,
          'pane': 'outline'
        });
      outline.addTo(map);
    });

    d3.json('assets/substrates/substrates.json', function(err, substratesData) {
      
      var divs = d3.select('#substrate-picker').selectAll('div')
        .data(substratesData)
        .enter()
        .append('div');

      divs.append('h2')
        .text(function(item) { return item.heading; });

      divs.each(function(heading) { 
        var labels = d3.select(this)
          .selectAll('label')
          .data(heading.items)
          .enter()
          .append('label');

        labels
          .append('input')
          .attr('type', 'radio')
          .attr('name', 'substrates')
          .on('change', setSubstrate);
        
        labels
          .append('span')
          .text(function (substrate) { return ' ' + substrate.label; });
        });



      d3.select('#substrate-picker input:first-of-type')
        .property('checked', true)
        .each(setSubstrate);

    });

  })();


})(window, document);
