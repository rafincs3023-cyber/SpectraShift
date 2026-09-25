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
    text: "When SPHEREx took the image. SpectraShift compares two dates: June 19 and December 17, 2025, about six months apart.",
  },
  differenceView: {
    term: "Difference image",
    text: "The later image minus the earlier image, so only what changed stands out. Red: brighter later; blue: brighter earlier.",
  },
  candidate: {
    term: "Two-epoch candidate",
    text: "A source whose position or appearance changed between the two observations enough to deserve a closer look. It is never a confirmed moving object or discovery.",
  },
  displacement: {
    term: "Displacement",
    text: "How far a source's position changed between the two images, as an angle on the sky in arcseconds (″). 1″ = 1/3600 of a degree.",
  },
  apparentMotion: {
    term: "Apparent motion",
    text: "The displacement divided by the 181.77 days between the two observations, in arcseconds per day. With only two dates this is an average, not a measured path.",
  },
  stationarySource: {
    term: "Stationary source",
    text: "A star or galaxy found at the same place in both images, so it is not moving.",
  },
  blend: {
    term: "Blend",
    text: "Two sources so close together on the image that they look like one.",
  },
} as const;

export type GlossaryKey = keyof typeof GLOSSARY;
