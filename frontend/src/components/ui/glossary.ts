/** Plain-language definitions shared by tooltips and the Help glossary, so
 * every page explains a term the same way. Keep entries short and accurate. */
export const GLOSSARY = {
  ra: {
    term: "RA (Right Ascension)",
    text: "The sky's east–west coordinate, like longitude on Earth. Measured in degrees.",
  },
  dec: {
    term: "Dec (Declination)",
    text: "The sky's north–south coordinate, like latitude on Earth. Measured in degrees.",
  },
  skyCoordinates: {
    term: "Sky coordinates",
    text: "RA and Dec: a position on the sky, like longitude and latitude on Earth.",
  },
  wavelength: {
    term: "Wavelength",
    text: "The “colour” of light. SPHEREx sees infrared light from about 0.75 to 5 µm (micrometres) — longer than the red light our eyes can see.",
  },
  channel: {
    term: "Channel",
    text: "One narrow wavelength slice. Spectral View has 102 channels, from the shortest wavelength (1) to the longest (102).",
  },
  spectrum: {
    term: "Spectrum",
    text: "How bright one point of the sky is at each wavelength. Stars, galaxies and dust each have a typical pattern.",
  },
  brightness: {
    term: "Brightness",
    text: "How much light arrives from that spot of sky. Measured as surface brightness in MJy/sr.",
  },
  unit: {
    term: "MJy/sr",
    text: "Mega-janskys per steradian: the standard astronomy unit for how bright an area of sky is.",
  },
  detector: {
    term: "Detector",
    text: "One of SPHEREx's six infrared sensors (D1–D6). Each one covers part of the wavelength range.",
  },
  observationDate: {
    term: "Observation date",
    text: "When SPHEREx took the image. Comparing different dates can reveal things that changed or moved.",
  },
  differenceView: {
    term: "Difference view",
    text: "The later image minus the earlier image, so only what changed stands out.",
  },
  candidate: {
    term: "Possible moving object (candidate)",
    text: "A source that seemed to move between observation dates. It stays a candidate until checked, and none is a confirmed discovery.",
  },
  stationarySource: {
    term: "Stationary source",
    text: "A star or galaxy that stays in the same place in every image, so it is not moving.",
  },
  blend: {
    term: "Blend",
    text: "Two sources so close together on the image that they look like one.",
  },
} as const;

export type GlossaryKey = keyof typeof GLOSSARY;
