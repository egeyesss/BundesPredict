"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { Banner } from "@/components/states/Banner";
import { useReducedMotion } from "@/components/signature/reduced-motion";
import { Wordmark } from "@/components/signature/Wordmark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { OtpInput, type OtpStatus } from "@/components/ui/otp-input";
import { CSRF_COOKIE, readCookie } from "@/lib/api/client";
import {
  ALLAUTH_BASE,
  confirmLoginCode,
  ensureCsrfCookie,
  requestLoginCode,
  signUp,
  verifyEmail,
  type AuthFailure,
} from "@/lib/auth/allauth";
import { navigate } from "@/lib/navigate";


const CODE_LENGTH = 8;
const RESEND_SECONDS = 30;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Mode = "signin" | "signup";
type Step = "email" | "code";

const SEND_ERRORS: Record<AuthFailure, string> = {
  invalid_email: "That doesn't look like an email address. Check for a typo.",
  rate_limited: "Too many codes requested. Wait a minute, then try again.",
  network: "Couldn't reach the server. Check your connection and try again.",
  invalid_code: "Couldn't send a code. Try again.",
  expired: "Couldn't send a code. Try again.",
  unexpected: "Couldn't send a code. Try again in a moment.",
};

const CONFIRM_ERRORS: Record<AuthFailure, string> = {
  invalid_code: "That code didn't work. Use the newest email, or resend a code.",
  expired: "That code expired or was tried too many times. Send a new one.",
  rate_limited: "Too many attempts. Wait a minute, then try again.",
  network: "Couldn't reach the server. Check your connection and try again.",
  invalid_email: "That code didn't work. Use the newest email, or resend a code.",
  unexpected: "Something went wrong checking the code. Try again.",
};

const clock = (seconds: number) => `0:${String(seconds).padStart(2, "0")}`;

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="size-[18px]">
      <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z" />
      <path fill="#FF3D00" d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z" />
      <path fill="#4CAF50" d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z" />
      <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z" />
    </svg>
  );
}

type LoginFormProps = {
  /** Already validated by `safeNextPath`. */
  next: string;
  socialError: boolean;
  /** The `?key=` from an emailed link, when there is one. */
  emailKey: string | null;
};

export function LoginForm({ next, socialError, emailKey }: LoginFormProps) {
  const reducedMotion = useReducedMotion(false);
  const [step, setStep] = useState<Step>("email");
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState("");
  const [sending, setSending] = useState(false);
  const [code, setCode] = useState("");
  const [otpStatus, setOtpStatus] = useState<OtpStatus>("idle");
  const [codeError, setCodeError] = useState("");
  const [notice, setNotice] = useState("");
  const [resendLeft, setResendLeft] = useState(0);
  const [keyError, setKeyError] = useState(false);
  const keyHandled = useRef(false);
  const googleForm = useRef<HTMLFormElement>(null);
  const csrfField = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void ensureCsrfCookie();
  }, []);

  useEffect(() => {
    if (!emailKey || keyHandled.current) return;
    keyHandled.current = true;
    verifyEmail(emailKey).then((result) => {
      if (result.ok) navigate(next);
      else setKeyError(true);
    });
  }, [emailKey, next]);

  useEffect(() => {
    if (resendLeft <= 0) return;
    const timer = setTimeout(() => setResendLeft((left) => left - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendLeft]);

  const sendCode = useCallback(
    async (address: string, forMode: Mode): Promise<boolean> => {
      setSending(true);
      const result = await (forMode === "signin" ? requestLoginCode(address) : signUp(address));
      setSending(false);
      if (!result.ok) {
        setEmailError(SEND_ERRORS[result.reason]);
        return false;
      }
      setCode("");
      setOtpStatus("idle");
      setCodeError("");
      setResendLeft(RESEND_SECONDS);
      return true;
    },
    [],
  );

  const handleEmailSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const address = email.trim();
    if (!EMAIL_PATTERN.test(address)) {
      setEmailError(address ? SEND_ERRORS.invalid_email : "Enter your email to get a code.");
      return;
    }
    setEmailError("");
    setNotice("");
    if (await sendCode(address, mode)) setStep("code");
  };

  const handleComplete = async (completed: string) => {
    setOtpStatus("verifying");
    setCodeError("");
    setNotice("Checking the code…");
    const result = await (mode === "signin" ? confirmLoginCode(completed) : verifyEmail(completed));
    if (result.ok) {
      setOtpStatus("success");
      setNotice("Signed in");
      setTimeout(() => navigate(next), reducedMotion ? 300 : 1300);
      return;
    }
    setNotice("");
    setCodeError(CONFIRM_ERRORS[result.reason]);
    setOtpStatus("error");
    if (result.reason === "expired") setResendLeft(0);
    // Let the shake play before the digits drop out and focus returns to the first slot.
    setTimeout(
      () => {
        setCode("");
        focusFirstSlot();
      },
      reducedMotion ? 0 : 520,
    );
  };

  const focusFirstSlot = () => document.querySelector<HTMLInputElement>("[data-otp-root] input")?.focus();

  const handleCodeChange = (value: string) => {
    setCode(value);
    if (otpStatus === "error") setOtpStatus("idle");
  };

  const resend = async () => {
    if (await sendCode(email.trim(), mode)) {
      setNotice(`New code sent to ${email.trim()}`);
      focusFirstSlot();
    }
  };

  const switchMode = async (nextMode: Mode) => {
    setMode(nextMode);
    setEmailError("");
    if (step === "code" && (await sendCode(email.trim(), nextMode))) {
      setNotice(`Code sent to ${email.trim()}`);
      focusFirstSlot();
    }
  };

  const handleGoogleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    const form = event.currentTarget;
    const existing = readCookie(document.cookie, CSRF_COOKIE);
    if (existing) {
      if (csrfField.current) csrfField.current.value = existing;
      return;
    }
    event.preventDefault();
    const fresh = await ensureCsrfCookie();
    if (csrfField.current) csrfField.current.value = fresh ?? "";
    form.submit();
  };

  if (step === "code") {
    const alternate: Mode = mode === "signin" ? "signup" : "signin";
    return (
      <div className="mx-auto grid w-full max-w-[440px] gap-5 text-center">
        <div className="grid gap-2">
          <span className="font-mono text-xs tracking-[0.08em] text-bp-text-muted uppercase">Check your inbox</span>
          <h1 className="font-display text-[30px] leading-none font-bold">Enter the 8-letter code</h1>
          <p className="text-bp-text-muted">
            We sent it to <b className="font-semibold text-bp-text">{email.trim()}</b>.
          </p>
        </div>
        <div data-otp-root>
          <OtpInput
            label="Sign-in code"
            length={CODE_LENGTH}
            separatorAfter={4}
            value={code}
            onChange={handleCodeChange}
            onComplete={handleComplete}
            status={otpStatus}
            disabled={sending}
            autoFocus
          />
        </div>
        <div className="min-h-[1.3em] text-[13px] text-bp-red-text" role="alert">
          {codeError}
        </div>
        <div className="flex min-h-[1.5em] items-center justify-center font-mono text-xs text-bp-text-muted" role="status">
          {notice}
        </div>
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-sm">
          <button type="button" className="link-quiet" disabled={resendLeft > 0 || sending} onClick={() => void resend()}>
            {resendLeft > 0 ? `Resend code in ${clock(resendLeft)}` : "Resend code"}
          </button>
          <span aria-hidden="true" className="text-bp-text-muted">
            ·
          </span>
          <button
            type="button"
            className="link-quiet"
            onClick={() => {
              setStep("email");
              setOtpStatus("idle");
              setCodeError("");
              setNotice("");
            }}
          >
            Use a different email
          </button>
        </div>
        <p className="text-xs text-bp-text-muted">
          {mode === "signin" ? "No account with this email yet? " : "Already have an account? "}
          <button type="button" className="link-quiet" disabled={sending} onClick={() => void switchMode(alternate)}>
            {mode === "signin" ? "Create one instead" : "Sign in instead"}
          </button>
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto grid w-full max-w-[400px] gap-5 text-center">
      <div className="flex justify-center">
        <Wordmark size="hero" className="!text-[46px]" />
      </div>
      <div className="grid gap-1.5">
        <h1 className="font-display text-[30px] leading-none font-bold">
          {mode === "signin" ? "Sign in to talk to the agent" : "Create your account"}
        </h1>
        <p className="text-bp-text-muted">3 free chats a day. Your chats are saved to your account.</p>
      </div>
      {(socialError || keyError) && (
        <Banner tone="crit" role="alert" icon="!" className="text-left">
          {keyError
            ? "That sign-in link expired. Enter your email to get a new code."
            : "Google sign-in didn't finish. Try again, or use an email code instead."}
        </Banner>
      )}
      <form
        ref={googleForm}
        method="post"
        action={`${ALLAUTH_BASE}/auth/provider/redirect`}
        onSubmit={handleGoogleSubmit}
        className="contents"
      >
        <input type="hidden" name="provider" value="google" />
        <input type="hidden" name="callback_url" value={next} />
        <input type="hidden" name="process" value="login" />
        <input type="hidden" name="csrfmiddlewaretoken" ref={csrfField} defaultValue="" />
        <Button type="submit" size="lg" className="w-full border-white bg-white text-[#1F1F1F] hover:bg-[#F2F2F2]">
          <GoogleMark />
          Continue with Google
        </Button>
      </form>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 font-mono text-xs text-bp-text-muted before:h-px before:bg-bp-border after:h-px after:bg-bp-border">
        or
      </div>
      <form className="grid gap-2" onSubmit={handleEmailSubmit} noValidate>
      <div className="grid gap-1.5 text-left">
        <label htmlFor="login-email" className="text-[13px] text-bp-text-muted">
          Email
        </label>
        <Input
          id="login-email"
          type="email"
          autoComplete="email"
          inputMode="email"
          placeholder="you@example.com"
          value={email}
          aria-invalid={emailError ? true : undefined}
          aria-describedby="login-email-error"
          onChange={(event) => {
            setEmail(event.target.value);
            if (emailError) setEmailError("");
          }}
        />
        <div id="login-email-error" className="min-h-[1.3em] text-[13px] text-bp-red-text" aria-live="polite">
          {emailError}
        </div>
      </div>
      <Button type="submit" size="lg" disabled={sending} className="w-full bg-bp-red text-white hover:bg-[#b80412]">
        {mode === "signin" ? "Email me a sign-in code" : "Email me a code"}
      </Button>
      </form>
      <p className="text-xs text-bp-text-muted">
        No password. We&apos;ll email you an 8-letter code that works for 3 minutes. By continuing you agree to the{" "}
        <Link href="/legal/terms" className="underline underline-offset-2">
          Terms
        </Link>{" "}
        and{" "}
        <Link href="/legal/privacy" className="underline underline-offset-2">
          Privacy Policy
        </Link>
        .
      </p>
      <div className="grid gap-1.5 text-xs text-bp-text-muted">
        <p>
          <button
            type="button"
            className="link-quiet"
            onClick={() => {
              setMode(mode === "signin" ? "signup" : "signin");
              setEmailError("");
            }}
          >
            {mode === "signin" ? "New here? Create an account" : "Already have an account? Sign in"}
          </button>
        </p>
        <p>
          Just looking?{" "}
          <Link href="/demo" className="link-quiet">
            Try the demo without an account
          </Link>
        </p>
      </div>
    </div>
  );
}
