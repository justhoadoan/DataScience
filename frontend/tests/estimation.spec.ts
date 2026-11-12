import { test, expect } from "@playwright/test";

test("estimate, distinguish studio from unknown, refresh changed inputs and inspect evidence", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Ước tính giá thuê" }),
  ).toBeVisible();
  const submit = page.getByRole("button", { name: "Xem giá thuê tham khảo" });
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(page.getByText("Chọn quận/huyện tại Hà Nội.")).toBeVisible();
  await page.getByLabel("Quận / huyện").selectOption("Hai Bà Trưng");
  await page.getByLabel("Diện tích sử dụng").fill("50");
  await page
    .getByRole("combobox", { name: "Phòng ngủ riêng Tuỳ chọn", exact: true })
    .selectOption("1");
  await submit.click();
  await expect(page.getByTestId("quote-price")).toBeVisible();
  const first = await page.getByTestId("quote-price").innerText();
  await page
    .getByRole("combobox", { name: "Phòng ngủ riêng Tuỳ chọn", exact: true })
    .selectOption("2");
  await expect(page.getByRole("status")).toContainText("Thông tin đã thay đổi");
  await expect(page.locator(".quote-context")).toContainText(
    "1 phòng ngủ riêng",
  );
  await page.getByRole("button", { name: "Ước tính lại", exact: true }).click();
  await expect(page.locator(".quote-context")).toContainText(
    "2 phòng ngủ riêng",
  );
  const second = await page.getByTestId("quote-price").innerText();
  const price = (s: string) => Number(s.split("\n")[0].replace(",", "."));
  expect(price(second)).toBeGreaterThanOrEqual(price(first));
  await expect(
    page.getByRole("heading", { name: "Tin gần diện tích này" }),
  ).toBeVisible();
  await page.getByLabel("Diện tích sử dụng").fill("10");
  await expect(page.getByRole("alert")).toContainText(
    "tối đa 0 phòng ngủ riêng",
  );
  expect(
    await page.locator("#bedrooms option").allTextContents(),
  ).not.toContain("5 phòng ngủ riêng");
  await page.getByRole("button", { name: "Ước tính lại", exact: true }).click();
  await expect(page.locator("#bedrooms")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await page
    .getByRole("combobox", { name: "Phòng ngủ riêng Tuỳ chọn", exact: true })
    .selectOption("0");
  await page.getByLabel("Phòng trọ", { exact: true }).check();
  const response = page.waitForResponse((r) =>
    r.url().endsWith("/api/predict"),
  );
  await page.getByRole("button", { name: "Ước tính lại", exact: true }).click();
  const res = await response;
  expect(res.request().postDataJSON().bedrooms).toBe(0);
  await expect(page.locator(".quote-context")).toContainText(
    "Studio · 0 phòng ngủ riêng",
  );
  await expect(page.locator(".warnings")).toContainText(
    "chưa dùng số phòng ngủ riêng",
  );
  await page
    .getByRole("combobox", { name: "Phòng ngủ riêng Tuỳ chọn", exact: true })
    .selectOption("");
  const unknown = page.waitForResponse((r) => r.url().endsWith("/api/predict"));
  await page.getByRole("button", { name: "Ước tính lại", exact: true }).click();
  expect((await unknown).request().postDataJSON().bedrooms).toBeNull();
  await expect(page.locator(".quote-context")).toContainText(
    "Chưa rõ phòng ngủ riêng",
  );
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Thị trường", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Giá chào theo khu vực" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/market-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Phòng trọ", exact: true }).click();
  await expect(page.locator(".district-grid").first()).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Về mô hình", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Phòng ngủ riêng khác số giường" }),
  ).toBeVisible();
  await expect(page.locator(".behavior-note")).toContainText("0 vi phạm");
  await page.screenshot({
    path: "test-results/model-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Ước tính giá", exact: true })
    .click();
  await expect(page.locator("#bedrooms")).toHaveValue("");
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `test-results/estimator-${width}.png`,
      fullPage: true,
    });
  }
});

test("edited input while a prediction is running never labels the old result as current", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Xem giá thuê tham khảo" }),
  ).toBeEnabled();
  await page.getByLabel("Quận / huyện").selectOption("Hai Bà Trưng");
  await page.route("**/api/predict", async (route) => {
    const response = await route.fetch();
    await new Promise((resolve) => setTimeout(resolve, 300));
    await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Xem giá thuê tham khảo" }).click();
  await page.getByLabel("Diện tích sử dụng").fill("80");
  await expect(page.getByTestId("quote-price")).toBeVisible();
  await expect(page.locator(".quote-context")).toContainText("50 m²");
  await expect(page.getByRole("status")).toContainText("Thông tin đã thay đổi");
});

test("phone supports studio input, estimation and folded navigation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const button = page.getByRole("button", { name: "Xem giá thuê tham khảo" });
  await expect(button).toBeEnabled();
  await expect(button).toBeInViewport();
  await page.getByLabel("Quận / huyện").selectOption("Hai Bà Trưng");
  await page.getByLabel("Phòng trọ", { exact: true }).check();
  await page.getByLabel("Diện tích sử dụng").fill("20");
  await page
    .getByRole("combobox", { name: "Phòng ngủ riêng Tuỳ chọn", exact: true })
    .selectOption("0");
  await button.click();
  await expect(page.locator(".quote-context")).toContainText(
    "Studio · 0 phòng ngủ riêng",
  );
  await page.getByTestId("quote-price").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "test-results/studio-mobile.png",
    fullPage: true,
  });
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Về mô hình", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Về mô hình", exact: true }),
  ).toBeVisible();
});

test("server validation is visible beside its field and connection errors can be retried", async ({
  page,
}) => {
  await page.goto("/");
  const button = page.getByRole("button", { name: "Xem giá thuê tham khảo" });
  await expect(button).toBeEnabled();
  await page.getByLabel("Quận / huyện").selectOption("Hai Bà Trưng");
  await page.route("**/api/predict", (route) =>
    route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({
        detail: [
          { loc: ["body", "bedrooms"], msg: "Bố trí phòng cần kiểm tra lại." },
        ],
      }),
    }),
  );
  await button.click();
  await expect(page.locator("#bedrooms-error")).toHaveText(
    "Bố trí phòng cần kiểm tra lại.",
  );
  await page.unroute("**/api/predict");
  await page.route("**/api/schema", (route) =>
    route.fulfill({ status: 503, body: "Unavailable" }),
  );
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("Dịch vụ chưa sẵn sàng");
  await expect(button).toBeDisabled();
  await page.unroute("**/api/schema");
  await page.getByRole("button", { name: "Thử lại" }).click();
  await expect(button).toBeEnabled();
});
