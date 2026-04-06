const chatForm = document.getElementById("chatForm");
const chatWindow = document.getElementById("chatWindow");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");

const modeSelect = document.getElementById("modeSelect");
const providerSelect = document.getElementById("providerSelect");
const backendSelect = document.getElementById("backendSelect");
const maxStepsInput = document.getElementById("maxStepsInput");
const modelSelect = document.getElementById("modelSelect");
const reasoningModal = document.getElementById("reasoningModal");
const closeReasoningBtn = document.getElementById("closeReasoningBtn");
const reasoningContent = document.getElementById("reasoningContent");

// Set up suggestion chips
const suggestionChips = document.querySelectorAll(".suggestion-chip");
suggestionChips.forEach(chip => {
  chip.addEventListener("click", () => {
    messageInput.value = chip.textContent;
    // Trigger submit event on the form
    chatForm.dispatchEvent(new Event("submit"));
  });
});

function appendMessage(text, role = "assistant") {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = text;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function appendMeta(text) {
  appendMessage(text, "meta");
}

function showTypingIndicator() {
  const div = document.createElement("div");
  div.className = "message assistant typing-message";
  
  const indicator = document.createElement("div");
  indicator.className = "typing-indicator";
  indicator.innerHTML = "<span></span><span></span><span></span>";
  
  div.appendChild(indicator);
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return div;
}

function removeTypingIndicator(element) {
  if (element && element.parentNode) {
    element.parentNode.removeChild(element);
  }
}

function formatReasoning(reasoning) {
  if (!Array.isArray(reasoning) || reasoning.length === 0) {
    return "No loop reasoning available for this response.";
  }

  return reasoning
    .map((item, index) => {
      const loopNum = item.step ?? index + 1;
      let traceBlock = `=== Loop ${loopNum} ===\n`;
      
      if (item.thought) {
        traceBlock += `Thought: ${item.thought}\n`;
      }
      if (item.action) {
        traceBlock += `Action:  ${item.action}\n`;
      } else if (item.status === 'guardrail_forced_tool') {
        traceBlock += `Action:  ${item.tool}()... (forced)\n`;
      }
      
      if (item.observation) {
        traceBlock += `Observation: ${item.observation}\n`;
      }
      if (item.parse_error) {
        traceBlock += `Parse Error: ${item.parse_error}\n`;
      }
      if (item.final_answer) {
        traceBlock += `Final Answer: ${item.final_answer}\n`;
      }
      
      return traceBlock.trim();
    })
    .join("\n\n");
}

function showReasoning(reasoning) {
  reasoningContent.textContent = formatReasoning(reasoning);
  reasoningModal.classList.remove("hidden");
}

function hideReasoning() {
  reasoningModal.classList.add("hidden");
}

function appendAssistantWithReasoning(answer, reasoning, metrics) {
  const wrap = document.createElement("div");
  wrap.className = "assistant-wrap";

  const message = document.createElement("div");
  message.className = "message assistant";
  message.textContent = answer || "(empty response)";
  wrap.appendChild(message);

  if (metrics && Object.keys(metrics).length > 0) {
    const metricsDiv = document.createElement("div");
    metricsDiv.className = "metrics-row";
    
    // Build strings for UI
    let statusIcon = "✅";
    if (metrics.status && metrics.status.includes("error")) statusIcon = "❌";
    else if (metrics.status === "max_steps" || metrics.status === "stopped_loop_guard" || metrics.status === "stopped_hallucinated_tool") statusIcon = "⚠️";
    
    let text = `${statusIcon} TT & Latency: ${metrics.total_latency_ms || 0}ms  •  Tokens: ${metrics.total_tokens || 0}  •  Steps: ${metrics.loop_count || 1}`;
    
    if (metrics.parse_errors > 0) text += `  •  Parse Errors: ${metrics.parse_errors}`;
    if (metrics.hallucinated_tools > 0) text += `  •  Hallucinated tools: ${metrics.hallucinated_tools}`;
    
    metricsDiv.textContent = text;
    wrap.appendChild(metricsDiv);
  }

  if (Array.isArray(reasoning) && reasoning.length > 0) {
    const details = document.createElement("details");
    details.className = "reasoning-details";
    
    const summary = document.createElement("summary");
    summary.className = "reasoning-summary";
    summary.textContent = "View ReAct Trace (Thought, Action, Observation)";
    details.appendChild(summary);

    const pre = document.createElement("pre");
    pre.className = "reasoning-inline-content";
    pre.textContent = formatReasoning(reasoning);
    details.appendChild(pre);

    wrap.appendChild(details);
  }

  chatWindow.appendChild(wrap);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function createAssistantCard(data, titleText) {
  const card = document.createElement("div");
  card.className = "compare-card";
  
  const title = document.createElement("div");
  title.className = "compare-title";
  title.textContent = titleText;
  card.appendChild(title);

  const message = document.createElement("div");
  message.className = "message assistant compare-msg";
  message.textContent = data.answer || "(empty response)";
  card.appendChild(message);

  if (data.metrics && Object.keys(data.metrics).length > 0) {
    const metricsDiv = document.createElement("div");
    metricsDiv.className = "metrics-row";
    
    let statusIcon = "✅";
    if (data.metrics.status && data.metrics.status.includes("error")) statusIcon = "❌";
    else if (data.metrics.status === "max_steps" || data.metrics.status.includes("stopped")) statusIcon = "⚠️";
    
    let text = `${statusIcon} TT & Lat: ${data.metrics.total_latency_ms || 0}ms • Tok: ${data.metrics.total_tokens || 0} • Loops: ${data.metrics.loop_count || 1}`;
    metricsDiv.textContent = text;
    card.appendChild(metricsDiv);
  }

  if (Array.isArray(data.reasoning) && data.reasoning.length > 0) {
    const details = document.createElement("details");
    details.className = "reasoning-details";
    const summary = document.createElement("summary");
    summary.className = "reasoning-summary";
    summary.textContent = "View ReAct Trace";
    details.appendChild(summary);

    const pre = document.createElement("pre");
    pre.className = "reasoning-inline-content";
    pre.textContent = formatReasoning(data.reasoning);
    details.appendChild(pre);
    card.appendChild(details);
  }
  return card;
}

function appendCompareAssistant(data1, data2) {
  const wrap = document.createElement("div");
  wrap.className = "assistant-compare-wrap";
  
  wrap.appendChild(createAssistantCard(data1, "Agent v1 (Baseline)"));
  wrap.appendChild(createAssistantCard(data2, "Agent v2 (Guardrails)"));
  
  chatWindow.appendChild(wrap);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

appendMeta("Connected. Ask about products, coupons, shipping, or total cost.");

const MODELS_BY_PROVIDER = {
  gemini: [
    { value: "gemini-3.1-flash-lite-preview", label: "Gemini 3.1 Flash Lite" },
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    { value: "gemini-3.0-flash", label: "Gemini 3 Flash" },
    { value: "gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite" },
  ],
  openai: [
    { value: "gpt-4o", label: "GPT-4o (default)" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
    { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
  ],
  local: [{ value: "local", label: "Local Phi-3 (CPU)" }],
};

function updateModelOptions() {
  const provider = providerSelect.value;
  const models = MODELS_BY_PROVIDER[provider] || [];
  modelSelect.innerHTML = models
    .map((m) => `<option value="${m.value}">${m.label}</option>`)
    .join("");
}

providerSelect.addEventListener("change", updateModelOptions);
updateModelOptions();

clearBtn.addEventListener("click", () => {
  chatWindow.innerHTML = "";
  appendMeta("Chat cleared.");
});

closeReasoningBtn.addEventListener("click", hideReasoning);
reasoningModal.addEventListener("click", (event) => {
  if (event.target === reasoningModal) {
    hideReasoning();
  }
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message) {
    return;
  }

  appendMessage(message, "user");
  messageInput.value = "";

  const payload = {
    message,
    mode: modeSelect.value,
    provider: providerSelect.value,
    backend: backendSelect.value,
    max_steps: Number(maxStepsInput.value || 6),
    model: modelSelect.value,
  };

  sendBtn.disabled = true;
  sendBtn.textContent = "Sending...";

    let typingEl = null;
    let typingEl2 = null;
    
  if (payload.mode === "compare") {
    appendMeta("Running both v1 and v2 simultaneously... please wait.");
    
    const wrap = document.createElement("div");
    wrap.className = "assistant-compare-wrap";
    const sim1 = showTypingIndicator();
    const sim2 = showTypingIndicator();
    wrap.appendChild(sim1);
    wrap.appendChild(sim2);
    chatWindow.appendChild(wrap);
    chatWindow.scrollTop = chatWindow.scrollHeight;
    
    try {
      const p1 = { ...payload, mode: "v1" };
      const p2 = { ...payload, mode: "v2" };
      
      const [res1, res2] = await Promise.all([
        fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(p1) }),
        fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(p2) })
      ]);
      
      wrap.parentNode.removeChild(wrap);
      
      if (!res1.ok || !res2.ok) throw new Error("One or both requests failed");
      
      const data1 = await res1.json();
      const data2 = await res2.json();
      
      appendCompareAssistant(data1, data2);
    } catch (err) {
      if (wrap && wrap.parentNode) wrap.parentNode.removeChild(wrap);
      appendMessage(`Error: ${err.message}`, "assistant");
    } finally {
      sendBtn.disabled = false;
      sendBtn.textContent = "Send";
      messageInput.focus();
    }
  } else {
    typingEl = showTypingIndicator();
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      removeTypingIndicator(typingEl);

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || "Request failed");
      }

      const data = await response.json();
      appendAssistantWithReasoning(data.answer, data.reasoning || [], data.metrics || {});
    } catch (error) {
      removeTypingIndicator(typingEl);
      appendMessage(`Error: ${error.message}`, "assistant");
    } finally {
      sendBtn.disabled = false;
      sendBtn.textContent = "Send";
      messageInput.focus();
    }
  }
});
