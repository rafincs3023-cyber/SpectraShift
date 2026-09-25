/** Plain colour key for a difference image. The meaning of red and blue
 * depends on which image was subtracted, so callers state it explicitly. */
export function DifferenceLegend({
  formula,
  red,
  blue,
}: {
  formula: string;
  red: string;
  blue: string;
}) {
  return (
    <div className="difference-caption">
      <p className="difference-convention">
        <strong>{formula}</strong>
      </p>
      <div className="diff-legend" role="list" aria-label="Colour key">
        <span role="listitem">
          <i className="swatch swatch-pos" /> Red = {red}
        </span>
        <span role="listitem">
          <i className="swatch swatch-neg" /> Blue = {blue}
        </span>
        <span role="listitem">
          <i className="swatch swatch-dark" /> Dark = little or no change
        </span>
      </div>
      <p className="callout-warning">
        A visible difference does not automatically mean a moving object. It
        can also come from brightness changes, slight differences between the
        two images, or bright-star artifacts.
      </p>
    </div>
  );
}
