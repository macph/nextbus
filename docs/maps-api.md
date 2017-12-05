# Notes on Google Maps

There are 3 main APIs provided by Google for showing maps:
- **Google Maps Embed API**
- **Google Maps JavaScript API**
- **Google Static Maps API**

Each differ in features provided, quota limits and processing load on the client. All APIs require a key to function.

## Google Maps Embed API

This is the most basic but also freely available API, with a limit of 2M loads/day. It consists of a simple `iframe` with URL pointing to a marker or a latitude & longitude location.

```html
<iframe width="600"
        height="450"
        frameborder="0"
        style="border:0"
        src="https://www.google.com/maps/embed/v1/place
        ?key=...
        &q=...
        &center=...
        &zoom=...
        &maptype=..." allowfullscreen>
</iframe> 
```
This produces a 600x450 map with a marker defined `q`, centred on `center` coordinate at scale `zoom`. Map types (`maptype`) can be defined as `roadmap` or `satellite`.

### StreetView

StreetView, which are 360-degree photos taken from the street, can be embedded as well.

```html
<iframe width="600"
        height="450"
        frameborder="0"
        style="border:0"
        src="https://www.google.com/maps/embed/v1/streetview
        ?key=...
        &location=...
        &heading=...
        &pitch=...
        &fov=..." allowfullscreen>
</iframe> 
```
The location is defined by latitude and longitude, and the heading/pitch/FOV can be set. Google Maps will find a photo nearest the specified location, but will not rotate to view the location automatically; to do so would require the JS API.

## Google Maps JavaScript API

...