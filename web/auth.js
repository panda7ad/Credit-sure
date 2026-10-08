const authForm = document.getElementById("auth-form");
const alertBox = document.getElementById("auth-alert");
const isSignUp = window.location.pathname === "/signup";
const isRecovery = !isSignUp && new URLSearchParams(window.location.search).get("recovery") === "1";
const isReauth = new URLSearchParams(window.location.search).get("reauth") === "1";
let captchaWidget;
let captchaToken = "";

async function configureCaptcha(config) {
  if (!config.captcha_site_key) return;
  const script = document.createElement("script");
  script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
  await new Promise((resolve, reject) => {
    script.onload = resolve;
    script.onerror = () => reject(new Error("The security check could not load. Please refresh."));
    document.head.append(script);
  });
  const container = document.createElement("div");
  authForm.insertBefore(container, document.getElementById("auth-submit"));
  captchaWidget = window.turnstile.render(container, { sitekey: config.captcha_site_key,
    callback: token => { captchaToken = token; },
    "expired-callback": () => { captchaToken = ""; }, "error-callback": () => { captchaToken = ""; } });
}

function resetCaptcha() {
  captchaToken = "";
  if (captchaWidget !== undefined) window.turnstile.reset(captchaWidget);
}

function showAuthMessage(message, kind = "error") {
  alertBox.textContent = message;
  alertBox.className = `auth-alert ${kind}`;
  alertBox.hidden = false;
}

function configureAuthPage() {
  const signup = isSignUp && !isRecovery;
  const recovery = isRecovery && !isSignUp;
  document.querySelector(".auth-aside .eyebrow").textContent =
    signup ? "A PRIVATE PLACE TO START" : recovery ? "ACCOUNT SECURITY" : "YOUR PRIVATE WORKSPACE";
  document.querySelector(".auth-aside > p:not(.eyebrow)").textContent =
    signup
      ? "Create an account to keep your research assessments private to you."
      : recovery
        ? "Choose a new password to keep your workspace secure."
        : "Sign in to save and review your own research assessments.";
  document.getElementById("auth-eyebrow").textContent = signup ? "A PRIVATE PLACE TO START" : recovery ? "ACCOUNT SECURITY" : "WELCOME BACK";
  document.getElementById("auth-title").textContent = signup ? "Create your account" : recovery ? "Choose a new password" : "Sign in";
  document.getElementById("auth-description").textContent = signup
    ? "Use your email to set up a private research workspace."
    : recovery ? "Choose a new password for your Credit-Sure account." : "Access the assessments saved to your account.";
  document.getElementById("auth-submit").innerHTML = signup
    ? 'Create account <span aria-hidden="true">→</span>'
    : recovery ? 'Save new password <span aria-hidden="true">→</span>' : 'Sign in <span aria-hidden="true">→</span>';
  document.getElementById("email-row").hidden = recovery;
  document.getElementById("email").required = !recovery;
  document.getElementById("password-label").textContent = recovery ? "New password" : "Password";
  document.getElementById("password").autocomplete = signup || recovery ? "new-password" : "current-password";
  document.getElementById("password").minLength = signup || recovery ? 12 : 1;
  document.getElementById("password").maxLength = 128;
  document.getElementById("confirm-password").minLength = 12;
  document.getElementById("confirm-password").maxLength = 128;
  document.getElementById("confirm-row").hidden = !signup && !recovery;
  document.getElementById("confirm-label").textContent = recovery ? "Confirm new password" : "Confirm password";
  document.getElementById("confirm-password").required = signup || recovery;
  document.getElementById("forgot-password").hidden = signup || recovery;
  document.getElementById("terms-row").hidden = !signup;
  document.getElementById("terms-check").required = signup;
  document.getElementById("auth-switch").innerHTML = signup
    ? 'Already have an account? <a href="/signin">Sign in</a>'
    : recovery ? 'Remembered your password? <a href="/signin">Return to sign in</a>'
      : 'New to Credit-Sure? <a href="/signup">Create an account</a>';
}

configureAuthPage();

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!authForm.reportValidity()) return;
  const submit = document.getElementById("auth-submit");
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;
  submit.disabled = true;
  alertBox.hidden = true;
  try {
    const setup = await window.creditSureReady;
    if (!setup) {
      showAuthMessage("Account access is not set up yet. The site owner must connect the Supabase project first.");
      return;
    }
    let result;
    if (isSignUp && !setup.config.signup_enabled) {
      showAuthMessage("New registration is temporarily closed."); return;
    }
    if (!isRecovery && setup.config.captcha_site_key && !captchaToken) {
      showAuthMessage("Complete the security check first."); return;
    }
    if (isRecovery) {
      if (!window.creditSureRecoveryActive) throw new Error("This reset link has expired. Request a new link from sign in.");
      if (password !== document.getElementById("confirm-password").value) {
        showAuthMessage("The passwords do not match.");
        return;
      }
      const { data } = await setup.client.auth.getSession();
      if (!data.session) throw new Error("This reset link has expired. Request a new link.");
      const result = await setup.client.auth.updateUser({ password });
      if (result.error) throw result.error;
      showAuthMessage("Your password has been updated. Your account is still signed in.", "success");
      window.history.replaceState({}, "", "/signin");
      document.getElementById("auth-title").textContent = "Password updated";
      document.getElementById("auth-submit").hidden = true;
      document.getElementById("auth-switch").innerHTML = '<a href="/workspace">Continue to your workspace</a>';
    } else if (isSignUp) {
      if (password !== document.getElementById("confirm-password").value) {
        showAuthMessage("The passwords do not match.");
        return;
      }
      result = await setup.client.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/workspace`,
          captchaToken: captchaToken || undefined
        }
      });
      if (result.error) throw result.error;
      if (result.data.session) {
        window.location.assign("/workspace");
      } else {
        showAuthMessage("Account created. Check your email to confirm your address, then sign in.", "success");
      }
    } else {
      result = await setup.client.auth.signInWithPassword({ email, password, options: { captchaToken: captchaToken || undefined } });
      if (result.error) throw result.error;
      window.location.assign("/workspace");
    }
  } catch (error) {
    showAuthMessage(error.message || "We could not complete that request. Please try again.");
  } finally {
    resetCaptcha();
    submit.disabled = false;
  }
});

document.getElementById("forgot-password").addEventListener("click", async () => {
  try {
    const setup = await window.creditSureReady;
    const email = document.getElementById("email").value.trim();
    if (!setup) {
      showAuthMessage("The site owner must connect Supabase before password recovery is available.");
      return;
    }
    if (!email || !document.getElementById("email").checkValidity()) {
      document.getElementById("email").reportValidity();
      return;
    }
    if (setup.config.captcha_site_key && !captchaToken) {
      showAuthMessage("Complete the security check first."); return;
    }
    const { error } = await setup.client.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/signin?recovery=1`, captchaToken: captchaToken || undefined
    });
    if (error) showAuthMessage(error.message);
    else showAuthMessage("If an account exists for this address, a password reset link will be sent.", "success");
  } catch (error) {
    showAuthMessage(error.message || "Password recovery is unavailable right now.");
  } finally {
    resetCaptcha();
  }
});

window.creditSureReady.then(async (setup) => {
  if (!setup) {
    showAuthMessage("Sign-up and sign-in will be available when the site owner completes Supabase setup.");
    return;
  }
  if (!isRecovery) await configureCaptcha(setup.config);
  if (isSignUp && !setup.config.signup_enabled) {
    document.getElementById("auth-submit").disabled = true;
    showAuthMessage("New registration is temporarily closed.");
  }
  if (isRecovery) {
    // The SDK emits implicit-flow recovery on the next event-loop turn.
    setup.client.auth.onAuthStateChange(event => {
      if (event === "PASSWORD_RECOVERY") {
        window.creditSureRecoveryActive = true;
        document.getElementById("auth-submit").disabled = false;
        alertBox.hidden = true;
      }
    });
    if (!window.creditSureRecoveryActive) {
      document.getElementById("auth-submit").disabled = true;
      showAuthMessage("This reset link is missing or expired. Return to sign in to request a new link.");
    }
    return;
  }
  if (isReauth) return;
  setup.client.auth.getSession().then(({ data }) => {
    if (data.session) window.location.replace("/workspace");
  });
}).catch((error) => showAuthMessage(error.message));
