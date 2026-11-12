export default function LayoutPreview({
  bedrooms,
  invalid,
}: {
  bedrooms: string;
  invalid: boolean;
}) {
  const count = bedrooms === "" ? null : Number(bedrooms);
  return (
    <div className="layout-preview">
      <svg
        viewBox="0 0 156 96"
        role="img"
        aria-label={
          count === null
            ? "Bố trí chưa rõ"
            : count === 0
              ? "Studio không có phòng ngủ riêng"
              : `${count} phòng ngủ riêng, sơ đồ khái niệm`
        }
      >
        <rect
          x="2"
          y="2"
          width="152"
          height="92"
          rx="3"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <path d="M112 2v28h42" fill="none" stroke="currentColor" />
        <rect
          x="126"
          y="9"
          width="17"
          height="12"
          rx="2"
          fill="none"
          stroke="currentColor"
        />
        {count !== null && !invalid && count > 0 ? (
          Array.from({ length: count }, (_, i) => (
            <g key={i}>
              <path
                d={`M${2 + (i * 110) / count} 2v52h${110 / count}`}
                stroke="currentColor"
                fill="none"
              />
              <rect
                x={10 + (i * 110) / count}
                y="13"
                width={Math.max(9, 110 / count - 18)}
                height="26"
                rx="2"
                fill="none"
                stroke="currentColor"
              />
            </g>
          ))
        ) : (
          <>
            <rect
              x="17"
              y="17"
              width="39"
              height="28"
              rx="2"
              fill="none"
              stroke="currentColor"
            />
            <path d="M20 25h33M74 72h26M78 63v18" stroke="currentColor" />
          </>
        )}
      </svg>
      <div>
        <strong>
          {invalid
            ? "Bố trí chưa phù hợp"
            : count === null
              ? "Bố trí chưa rõ"
              : count === 0
                ? "Studio · không ngăn phòng ngủ"
                : `${count} phòng ngủ riêng`}
        </strong>
        <p>
          {count === 0
            ? "Giường, bếp và WC có thể cùng trong một phòng khép kín."
            : "Đếm phòng có ngăn riêng để ngủ, không đếm giường hoặc khu bếp."}
        </p>
        <small>Minh hoạ khái niệm, không phải mặt bằng thực.</small>
      </div>
    </div>
  );
}
