import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw/http";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "@/lib/api/mocks/node";
import { setupApiMocks } from "@/lib/api/mocks/vitest";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@/lib/navigate", () => ({ navigate }));
vi.mock("@/components/signature/Wordmark", () => ({ Wordmark: () => <span>BundesPredict</span> }));

import { LoginForm } from "./LoginForm";

setupApiMocks();

beforeEach(() => navigate.mockReset());

const renderForm = (props: Partial<React.ComponentProps<typeof LoginForm>> = {}) =>
  render(<LoginForm next="/matchday" socialError={false} emailKey={null} {...props} />);

async function reachCodeStep(user: ReturnType<typeof userEvent.setup>, buttonName = "Email me a sign-in code") {
  await user.type(screen.getByLabelText("Email"), "sam.rivera@example.com");
  await user.click(screen.getByRole("button", { name: buttonName }));
  await screen.findByRole("heading", { name: "Enter the 8-letter code" });
}

async function typeCode(user: ReturnType<typeof userEvent.setup>, code: string) {
  // The first slot takes focus only after the code request resolves; typing earlier is lost.
  await waitFor(() => expect(screen.getByRole("textbox", { name: "Character 1 of 8" })).toHaveFocus());
  await user.keyboard(code);
}

describe("LoginForm email step", () => {
  it("posts the Google form to allauth with the callback path and login process", () => {
    renderForm({ next: "/account" });
    const form = screen.getByRole("button", { name: "Continue with Google" }).closest("form")!;
    expect(form).toHaveAttribute("method", "post");
    expect(form).toHaveAttribute("action", "/_allauth/browser/v1/auth/provider/redirect");
    expect(form.querySelector("[name=provider]")).toHaveValue("google");
    expect(form.querySelector("[name=callback_url]")).toHaveValue("/account");
    expect(form.querySelector("[name=process]")).toHaveValue("login");
  });

  it("validates the address before calling the server", async () => {
    const user = userEvent.setup();
    let called = false;
    server.use(http.post("*/auth/code/request", () => ((called = true), HttpResponse.json({}))));
    renderForm();
    await user.type(screen.getByLabelText("Email"), "nope");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in code" }));
    expect(await screen.findByText(/doesn't look like an email address/)).toBeInTheDocument();
    expect(called).toBe(false);
  });

  it("asks for an email when the field is empty", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.click(screen.getByRole("button", { name: "Email me a sign-in code" }));
    expect(await screen.findByText("Enter your email to get a code.")).toBeInTheDocument();
  });

  it("shows server-side send failures on the field", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.type(screen.getByLabelText("Email"), "limited@example.com");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in code" }));
    expect(await screen.findByText(/Too many codes requested/)).toBeInTheDocument();
  });

  it("switches to sign-up copy and calls signup instead of the login code", async () => {
    const user = userEvent.setup();
    const paths: string[] = [];
    server.events.on("request:start", ({ request }) => paths.push(new URL(request.url).pathname));
    renderForm();
    await user.click(screen.getByRole("button", { name: "New here? Create an account" }));
    expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    await reachCodeStep(user, "Email me a code");
    expect(paths).toContain("/_allauth/browser/v1/auth/signup");
    expect(paths).not.toContain("/_allauth/browser/v1/auth/code/request");
    server.events.removeAllListeners();
  });

  it("explains a failed Google round trip", () => {
    renderForm({ socialError: true });
    expect(screen.getByRole("alert")).toHaveTextContent("Google sign-in didn't finish");
  });
});

describe("LoginForm code step", () => {
  it("signs in with the right code and navigates to next", async () => {
    const user = userEvent.setup();
    renderForm({ next: "/account" });
    await reachCodeStep(user);
    await typeCode(user, "BCDFGHJK");
    expect(await screen.findByText("Signed in")).toBeInTheDocument();
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/account"), { timeout: 3000 });
  });

  it("shows the error, clears the slots and refocuses the first one after a wrong code", async () => {
    const user = userEvent.setup();
    renderForm();
    await reachCodeStep(user);
    await typeCode(user, "ZZZZZZZZ");
    expect(await screen.findByText(/That code didn't work/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole("textbox")[0]).toHaveValue(""));
    expect(navigate).not.toHaveBeenCalled();
  });

  it("asks for a new code when the flow expired", async () => {
    const user = userEvent.setup();
    renderForm();
    await reachCodeStep(user);
    server.use(http.post("*/auth/code/confirm", () => HttpResponse.json({ status: 401, data: { flows: [] } }, { status: 401 })));
    await typeCode(user, "BCDFGHJK");
    expect(await screen.findByText(/expired or was tried too many times/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resend code" })).toBeEnabled();
  });

  it("holds the resend button for 30 seconds", async () => {
    const user = userEvent.setup();
    renderForm();
    await reachCodeStep(user);
    expect(screen.getByRole("button", { name: "Resend code in 0:30" })).toBeDisabled();
  });

  it("lets the user turn a sign-in attempt into a sign-up for the same address", async () => {
    const user = userEvent.setup();
    renderForm();
    await reachCodeStep(user);
    let releaseSignup!: () => void;
    const signupHeld = new Promise<void>((resolve) => (releaseSignup = resolve));
    // Returning nothing hands the request on to the default signup handler once released.
    server.use(http.post("*/auth/signup", async () => void (await signupHeld)));
    await user.click(screen.getByRole("button", { name: "Create one instead" }));
    expect(await screen.findByRole("button", { name: "Sign in instead" })).toBeInTheDocument();
    const firstSlot = screen.getByRole("textbox", { name: "Character 1 of 8" });
    // A code typed before the new flow exists would be checked against the old one.
    expect(firstSlot).toHaveAttribute("readonly");
    releaseSignup();
    await waitFor(() => expect(firstSlot).not.toHaveAttribute("readonly"));
    // One paste keeps this about which flow gets the code; typing is covered in the auth e2e spec.
    await user.paste("BCDFGHJK");
    expect(await screen.findByText("Signed in")).toBeInTheDocument();
  });

  it("goes back to the email step with the address kept", async () => {
    const user = userEvent.setup();
    renderForm();
    await reachCodeStep(user);
    await user.click(screen.getByRole("button", { name: "Use a different email" }));
    expect(screen.getByLabelText("Email")).toHaveValue("sam.rivera@example.com");
  });
});

describe("LoginForm emailed link", () => {
  it("verifies the key from the link and continues", async () => {
    server.use(http.post("*/auth/email/verify", () => HttpResponse.json({ status: 200 })));
    renderForm({ emailKey: "abc", next: "/chat" });
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/chat"));
  });

  it("tells the user when the link is stale", async () => {
    server.use(http.post("*/auth/email/verify", () => HttpResponse.json({ status: 400 }, { status: 400 })));
    renderForm({ emailKey: "abc" });
    expect(await screen.findByRole("alert")).toHaveTextContent("That sign-in link expired");
  });
});
