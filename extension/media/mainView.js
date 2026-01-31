"use strict";
(() => {
  // webview/state.ts
  function createState() {
    return {
      currentMode: "ask",
      currentModel: "qwen",
      currentWorkflowId: null,
      currentAssistantMsg: null,
      totalSteps: 0,
      completedSteps: 0,
      codeRunTimer: null,
      codeRunStart: 0,
      codeRunActive: false,
      codeRunHasFinal: false,
      currentCodeStatus: "",
      cancelRequested: false,
      lastActionMilestone: null,
      activeStepIndex: null,
      stepEventContainers: {},
      stepMilestoneContainers: {},
      stepStatusLabels: {},
      currentSources: null
    };
  }

  // webview/ui.ts
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
  function scrollToBottom() {
    const container = document.getElementById("chat-container");
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }
  function highlightCode(code, lang) {
    const cKeywords = /\b(auto|break|case|char|const|continue|default|do|double|else|enum|extern|float|for|goto|if|int|long|register|return|short|signed|sizeof|static|struct|switch|typedef|union|unsigned|void|volatile|while|NULL|true|false|nullptr|class|public|private|protected|virtual|override|template|typename|namespace|using|new|delete|try|catch|throw|inline|constexpr|noexcept)\b/g;
    const pyKeywords = /\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|try|while|with|yield|True|False|self)\b/g;
    const types = /\b(TEE_Result|TEE_Param|TEE_ObjectHandle|TEE_OperationHandle|uint32_t|uint8_t|int32_t|size_t|bool|string|int|str|list|dict|tuple|set)\b/g;
    const strings = /("([^"\\]|\\.)*"|'([^'\\]|\\.)*')/g;
    const comments = /(\/\/.*$|\/\*[\s\S]*?\*\/|#.*$)/gm;
    const numbers = /\b(0x[0-9a-fA-F]+|\d+\.?\d*)\b/g;
    const functions = /\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()/g;
    const preprocessor = /^\s*(#\w+)/gm;
    let result = code;
    result = result.replace(comments, '<span class="hljs-comment">$1</span>');
    result = result.replace(strings, '<span class="hljs-string">$1</span>');
    result = result.replace(preprocessor, '<span class="hljs-meta">$1</span>');
    result = result.replace(numbers, '<span class="hljs-number">$1</span>');
    result = result.replace(types, '<span class="hljs-type">$1</span>');
    if (lang === "python" || lang === "py") {
      result = result.replace(pyKeywords, '<span class="hljs-keyword">$1</span>');
    } else {
      result = result.replace(cKeywords, '<span class="hljs-keyword">$1</span>');
    }
    result = result.replace(functions, '<span class="hljs-function">$1</span>');
    return result;
  }
  function renderMarkdown(text) {
    if (!text)
      return "";
    let result = text.replace(/\`\`\`(\w*)\n([\s\S]*?)\`\`\`/g, (match, lang, code) => {
      const highlighted = highlightCode(escapeHtml(code), lang);
      return '<pre><code class="language-' + lang + '">' + highlighted + "</code></pre>";
    });
    const unclosedMatch = result.match(/\`\`\`(\w*)\n([\s\S]*)$/);
    if (unclosedMatch) {
      const lang = unclosedMatch[1];
      const code = unclosedMatch[2];
      const highlighted = highlightCode(escapeHtml(code), lang);
      result = result.replace(/\`\`\`(\w*)\n([\s\S]*)$/, '<pre><code class="language-' + lang + '">' + highlighted + "</code></pre>");
    }
    result = result.replace(/((?:^\|.+\|\s*$\n?)+)/gm, (tableMatch) => {
      const lines = tableMatch.trim().split("\n").filter((line) => line.trim());
      if (lines.length < 2)
        return tableMatch;
      const hasSeparator = lines.some((line) => /^\s*\|[\s|:-]+\|\s*$/.test(line) && line.includes("-"));
      if (!hasSeparator)
        return tableMatch;
      let html = "<table>";
      let inHeader = true;
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (/^\s*\|[\s|:-]+\|\s*$/.test(line) && line.includes("-")) {
          inHeader = false;
          continue;
        }
        const cells = line.split("|").slice(1, -1).map((c) => c.trim());
        const tag = inHeader ? "th" : "td";
        html += "<tr>" + cells.map((c) => "<" + tag + ">" + c + "</" + tag + ">").join("") + "</tr>";
      }
      html += "</table>";
      return html;
    });
    return result.replace(/\`([^\`]+)\`/g, "<code>$1</code>").replace(/^#### (.+)$/gm, "<h4>$1</h4>").replace(/^### (.+)$/gm, "<h3>$1</h3>").replace(/^## (.+)$/gm, "<h2>$1</h2>").replace(/^# (.+)$/gm, "<h1>$1</h1>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/^- (.+)$/gm, "<li>$1</li>").replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>").replace(/^\d+\. (.+)$/gm, "<li>$1</li>").replace(/\n\n/g, "</p><p>").replace(/\n/g, "<br>");
  }
  function addAssistantMessage(state2, statusText = "\u6B63\u5728\u601D\u8003") {
    const container = document.getElementById("chat-container");
    const msg = document.createElement("div");
    msg.className = "message message-assistant";
    msg.innerHTML = '<div class="message-content"><div class="working-indicator">' + statusText + "</div></div>";
    container?.appendChild(msg);
    scrollToBottom();
    state2.currentAssistantMsg = msg;
    return msg;
  }
  function updateWorkingStatus(msg, statusText) {
    const indicator = msg.querySelector(".working-indicator");
    if (indicator) {
      indicator.textContent = statusText;
    }
  }
  function updateAssistantMessage(msg, content, sources = null) {
    let html = "";
    if (sources && sources.length > 0) {
      html += '<details class="sources-collapse"><summary>\u2713 \u68C0\u7D22\u5230 ' + sources.length + " \u4E2A\u76F8\u5173\u6587\u6863</summary>";
      html += '<div class="sources-content">';
      sources.forEach((s) => {
        const filename = s.source.split("/").pop();
        const score = Math.round(s.score * 100);
        html += '<div class="source-item">' + filename + ' <span style="opacity:0.6">(' + score + "%)</span></div>";
      });
      html += "</div></details>";
    }
    html += '<div class="markdown-content">' + renderMarkdown(content) + "</div>";
    msg.querySelector(".message-content").innerHTML = html;
    scrollToBottom();
  }
  function addAgentEvent(msg, type, content, containerOverride = null) {
    let eventContainer = containerOverride || msg.querySelector(".code-details .agent-events") || msg.querySelector(".agent-events");
    if (!eventContainer) {
      msg.querySelector(".message-content").innerHTML = '<div class="agent-events"></div>';
      eventContainer = msg.querySelector(".agent-events");
    }
    const event = document.createElement("div");
    event.className = "agent-event event-" + type;
    const label = document.createElement("div");
    label.className = "event-label";
    switch (type) {
      case "thought":
        label.textContent = "\u{1F4AD} \u601D\u8003";
        break;
      case "action":
        label.textContent = "\u{1F527} \u884C\u52A8";
        break;
      case "observation":
        label.textContent = "\u{1F441} \u89C2\u5BDF";
        break;
    }
    event.appendChild(label);
    const contentEl = document.createElement("div");
    contentEl.textContent = typeof content === "string" ? content : JSON.stringify(content, null, 2);
    event.appendChild(contentEl);
    eventContainer.appendChild(event);
    scrollToBottom();
  }
  function addMilestone(text, status, containerOverride = null) {
    const container = containerOverride || document.querySelector(".code-milestones");
    const item = document.createElement("div");
    item.className = "milestone " + status;
    item.textContent = text;
    container?.appendChild(item);
    return item;
  }
  function updateMilestone(item, status) {
    if (!item)
      return;
    item.className = "milestone " + status;
  }
  function initCodeRunView(state2, msg) {
    msg.querySelector(".message-content").innerHTML = '<div class="code-run"><div class="code-status">\u6267\u884C\u4E2D</div><div class="code-steps"></div><details class="code-details" open><summary>\u6267\u884C\u8BE6\u60C5</summary><div class="agent-events"></div></details></div>';
    state2.stepEventContainers = {};
    state2.stepMilestoneContainers = {};
    state2.stepStatusLabels = {};
  }
  function updateCodeStatus(state2, statusText) {
    state2.currentCodeStatus = statusText;
    if (!state2.currentAssistantMsg)
      return;
    const statusEl = state2.currentAssistantMsg.querySelector(".code-status");
    if (statusEl) {
      statusEl.textContent = statusText;
    }
    const indicator = state2.currentAssistantMsg.querySelector(".working-indicator");
    if (indicator) {
      indicator.textContent = statusText;
    }
  }
  function setStopButtonState(enabled, label = "\u505C\u6B62\u6267\u884C") {
    const stopBtn = document.getElementById("stop-btn");
    if (!stopBtn)
      return;
    stopBtn.disabled = enabled;
    stopBtn.textContent = label;
  }
  function ensureStepBlock(state2, stepIndex, step) {
    if (!state2.currentAssistantMsg)
      return;
    const codeRun = state2.currentAssistantMsg.querySelector(".code-run");
    if (!codeRun)
      return;
    const stepsContainer = codeRun.querySelector(".code-steps");
    if (!stepsContainer)
      return;
    const existing = stepsContainer.querySelector(`#code-step-${stepIndex}`);
    if (existing)
      return;
    const stepEl = document.createElement("div");
    stepEl.className = "code-step";
    stepEl.id = `code-step-${stepIndex}`;
    stepEl.innerHTML = '<div class="code-step-header"><div class="code-step-title">\u6B65\u9AA4 ' + (step?.id || stepIndex + 1) + ": " + (step?.description || "") + '</div><div class="code-step-status">\u8FDB\u884C\u4E2D</div></div><div class="code-step-milestones"></div><div class="agent-events"></div>';
    stepsContainer.appendChild(stepEl);
    state2.stepEventContainers[stepIndex] = stepEl.querySelector(".agent-events");
    state2.stepMilestoneContainers[stepIndex] = stepEl.querySelector(".code-step-milestones");
    state2.stepStatusLabels[stepIndex] = stepEl.querySelector(".code-step-status");
  }
  function setStepStatus(state2, stepIndex, statusText) {
    const status = state2.stepStatusLabels[stepIndex];
    if (status) {
      status.textContent = statusText;
    }
  }
  function setAllStepStatuses(state2, statusText, onlyInProgress = false) {
    Object.keys(state2.stepStatusLabels).forEach((key) => {
      const status = state2.stepStatusLabels[Number(key)];
      if (!status)
        return;
      if (onlyInProgress && status.textContent !== "\u8FDB\u884C\u4E2D")
        return;
      status.textContent = statusText;
    });
  }
  function showFinalResult(msg, answer) {
    const codeRun = msg.querySelector(".code-run");
    if (codeRun) {
      let result = codeRun.querySelector(".code-result");
      if (!result) {
        result = document.createElement("div");
        result.className = "code-result";
        const details = codeRun.querySelector(".code-details");
        if (details) {
          codeRun.insertBefore(result, details);
        }
      }
      result.innerHTML = '<div class="markdown-content">' + renderMarkdown(answer) + "</div>";
    } else {
      const eventContainer = msg.querySelector(".agent-events");
      if (eventContainer) {
        eventContainer.innerHTML += '<div class="markdown-content" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--vscode-panel-border);">' + renderMarkdown(answer) + "</div>";
      } else {
        msg.querySelector(".message-content").innerHTML = '<div class="markdown-content">' + renderMarkdown(answer) + "</div>";
      }
    }
    scrollToBottom();
  }
  function showPlanSteps(state2, msg, steps, workflowId, handlers) {
    state2.currentWorkflowId = workflowId;
    state2.totalSteps = steps.length;
    let html = '<div class="plan-card">';
    html += '<div class="plan-header">';
    html += "<div>";
    html += '<div class="plan-title">\u8BA1\u5212\u9884\u89C8</div>';
    html += '<div class="plan-meta">\u5171 ' + steps.length + " \u6B65 \xB7 \u786E\u8BA4\u540E\u81EA\u52A8\u6267\u884C</div>";
    html += "</div>";
    html += '<div class="plan-actions-inline">';
    html += '<button class="quick-action" id="refine-toggle">\u4FEE\u6539\u8BA1\u5212</button>';
    html += '<button class="quick-action btn-primary" id="confirm-btn">\u2713 \u786E\u8BA4\u6267\u884C</button>';
    html += "</div>";
    html += "</div>";
    html += '<div class="plan-steps">';
    steps.forEach((s, i) => {
      const stepLabel = s.id || i + 1;
      html += '<div class="plan-step" id="step-' + i + '">';
      html += '<div class="plan-step-index">' + escapeHtml(String(stepLabel)) + "</div>";
      html += '<div class="plan-step-text">' + escapeHtml(s.description || "") + "</div>";
      html += "</div>";
    });
    html += "</div>";
    html += '<div class="plan-refine hidden" id="refine-panel">';
    html += '<div class="plan-refine-title">\u4FEE\u6539\u8BA1\u5212</div>';
    html += '<textarea id="refine-input" placeholder="\u4F8B\u5982\uFF1A\u5408\u5E76\u6B65\u9AA4 2 \u548C 3\uFF0C\u5220\u9664\u6B65\u9AA4 4"></textarea>';
    html += '<div class="plan-refine-actions">';
    html += '<button class="quick-action" id="refine-btn">\u5E94\u7528\u4FEE\u6539</button>';
    html += '<button class="quick-action" id="refine-cancel">\u53D6\u6D88</button>';
    html += "</div>";
    html += "</div>";
    html += "</div>";
    msg.querySelector(".message-content").innerHTML = html;
    const refinePanel = document.getElementById("refine-panel");
    const refineToggle = document.getElementById("refine-toggle");
    const refineInput = document.getElementById("refine-input");
    const refineCancel = document.getElementById("refine-cancel");
    refineToggle.onclick = () => {
      refinePanel.classList.toggle("hidden");
      refineToggle.textContent = refinePanel.classList.contains("hidden") ? "\u4FEE\u6539\u8BA1\u5212" : "\u6536\u8D77\u4FEE\u6539";
      if (!refinePanel.classList.contains("hidden")) {
        refineInput.focus();
      }
    };
    refineCancel.onclick = () => {
      refinePanel.classList.add("hidden");
      refineToggle.textContent = "\u4FEE\u6539\u8BA1\u5212";
      refineInput.value = "";
    };
    const refineBtn = document.getElementById("refine-btn");
    refineBtn.onclick = () => {
      const instruction = refineInput.value.trim();
      if (instruction) {
        handlers.onRefine(instruction);
      }
    };
    const confirmBtn = document.getElementById("confirm-btn");
    confirmBtn.onclick = () => handlers.onConfirm();
    refineInput.onkeydown = (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        const instruction = refineInput.value.trim();
        if (instruction) {
          handlers.onRefine(instruction);
        }
      }
    };
    scrollToBottom();
  }
  function getActiveMilestoneContainer(state2) {
    if (state2.activeStepIndex !== null && state2.stepMilestoneContainers[state2.activeStepIndex]) {
      return state2.stepMilestoneContainers[state2.activeStepIndex];
    }
    if (!state2.currentAssistantMsg)
      return null;
    return state2.currentAssistantMsg.querySelector(".code-milestones");
  }
  function getActiveEventContainer(state2) {
    if (state2.activeStepIndex !== null && state2.stepEventContainers[state2.activeStepIndex]) {
      return state2.stepEventContainers[state2.activeStepIndex];
    }
    if (!state2.currentAssistantMsg)
      return null;
    return state2.currentAssistantMsg.querySelector(".code-details .agent-events") || state2.currentAssistantMsg.querySelector(".agent-events");
  }
  function maybeAddFileMilestone(state2, content, containerOverride = null) {
    if (!content || typeof content !== "string")
      return;
    if (!content.includes("path"))
      return;
    const match = content.match(/path['":\s]+([^'"\s,}]+)/);
    if (match && match[1]) {
      addMilestone("\u751F\u6210\u6587\u4EF6 " + match[1], "success", containerOverride);
    }
  }
  function formatElapsed(ms) {
    const totalSeconds = Math.floor(ms / 1e3);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    if (minutes === 0)
      return `${seconds}s`;
    return `${minutes}m${seconds}s`;
  }

  // webview/events.ts
  function bindDomEvents(state2, vscode2) {
    document.addEventListener("click", () => {
      document.querySelectorAll(".dropdown-menu").forEach((m) => m.classList.remove("show"));
    });
    setupDropdown("mode-dropdown", "mode-menu", (item) => {
      state2.currentMode = item.dataset.mode;
      document.getElementById("mode-icon").textContent = item.querySelector("span").textContent || "";
      document.getElementById("mode-text").textContent = item.querySelectorAll("span")[1].textContent || "";
      const placeholders = {
        ask: "\u8F93\u5165\u60A8\u7684\u95EE\u9898...",
        agent: "\u63CF\u8FF0\u60A8\u8981\u5B8C\u6210\u7684\u4EFB\u52A1..."
      };
      document.getElementById("main-input").placeholder = placeholders[state2.currentMode];
      vscode2.postMessage({ command: "switchMode", mode: state2.currentMode });
    });
    setupDropdown("model-dropdown", "model-menu", (item) => {
      state2.currentModel = item.dataset.model;
      document.getElementById("model-text").textContent = state2.currentModel;
      vscode2.postMessage({ command: "switchModel", model: state2.currentModel });
    });
    document.getElementById("send-btn").onclick = () => sendMessage(state2, vscode2);
    document.getElementById("main-input").onkeydown = (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        sendMessage(state2, vscode2);
      }
    };
    document.querySelectorAll(".quick-action[data-prompt]").forEach((btn) => {
      btn.onclick = () => {
        document.getElementById("main-input").value = btn.dataset.prompt || "";
        document.getElementById("main-input").focus();
      };
    });
    const stopBtn = document.getElementById("stop-btn");
    if (stopBtn) {
      stopBtn.onclick = () => requestCancel(state2, vscode2);
    }
  }
  function bindMessageEvents(state2, vscode2) {
    window.addEventListener("message", (event) => {
      const message = event.data;
      switch (message.command) {
        case "askResponse":
          if (state2.currentAssistantMsg) {
            updateAssistantMessage(state2.currentAssistantMsg, message.content, state2.currentSources);
          }
          break;
        case "sources":
          state2.currentSources = message.sources;
          break;
        case "status":
          if (state2.currentAssistantMsg) {
            updateWorkingStatus(state2.currentAssistantMsg, message.status);
          }
          break;
        case "planResponse":
          if (state2.currentAssistantMsg) {
            showPlanSteps(state2, state2.currentAssistantMsg, message.steps, message.workflowId, {
              onRefine: (instruction) => {
                if (instruction && state2.currentWorkflowId) {
                  vscode2.postMessage({ command: "refinePlan", workflowId: state2.currentWorkflowId, instruction });
                }
              },
              onConfirm: () => {
                if (state2.currentWorkflowId) {
                  vscode2.postMessage({ command: "confirmPlan", workflowId: state2.currentWorkflowId });
                }
              }
            });
          }
          break;
        case "planConfirmed":
          state2.currentAssistantMsg = addAssistantMessage(state2);
          break;
        case "setMode":
          const modeEl = document.querySelector('[data-mode="' + message.mode + '"]');
          modeEl?.click();
          break;
        case "codeStart":
          startCodeRun(state2);
          break;
        case "stepStart":
          if (state2.currentAssistantMsg) {
            const stepIndex = message.stepIndex;
            state2.activeStepIndex = stepIndex;
            ensureStepBlock(state2, stepIndex, message.step);
            setStepStatus(state2, stepIndex, "\u8FDB\u884C\u4E2D");
          }
          break;
        case "stepComplete":
          if (state2.currentAssistantMsg) {
            const stepIndex = message.stepIndex;
            setStepStatus(state2, stepIndex, "\u5B8C\u6210");
          }
          break;
        case "thought":
          if (state2.currentAssistantMsg) {
            const container = getActiveEventContainer(state2);
            addAgentEvent(state2.currentAssistantMsg, "thought", message.content, container);
          }
          break;
        case "action":
          if (state2.currentAssistantMsg) {
            const label = formatActionLabel(message.tool, message.input);
            const milestoneContainer = getActiveMilestoneContainer(state2);
            state2.lastActionMilestone = addMilestone(label, "pending", milestoneContainer);
            const container = getActiveEventContainer(state2);
            addAgentEvent(state2.currentAssistantMsg, "action", message.tool + ": " + JSON.stringify(message.input), container);
          }
          break;
        case "observation":
          if (state2.currentAssistantMsg) {
            let status = "success";
            if (typeof message.success === "boolean") {
              status = message.success ? "success" : "fail";
            } else {
              status = isFailureObservation(message.content) ? "fail" : "success";
            }
            updateMilestone(state2.lastActionMilestone, status);
            const container = getActiveEventContainer(state2);
            addAgentEvent(state2.currentAssistantMsg, "observation", message.content, container);
            const milestoneContainer = getActiveMilestoneContainer(state2);
            maybeAddFileMilestone(state2, message.content, milestoneContainer);
          }
          break;
        case "codeResult":
          if (state2.currentAssistantMsg) {
            showFinalResult(state2.currentAssistantMsg, message.answer);
          }
          state2.codeRunHasFinal = true;
          finishCodeRun(state2, "\u2705 \u6267\u884C\u5B8C\u6210");
          state2.currentSources = null;
          break;
        case "codeComplete":
          if (!state2.codeRunHasFinal && state2.cancelRequested) {
            finishCodeRun(state2, "\u{1F6D1} \u5DF2\u53D6\u6D88");
            setStopButtonState(true, "\u5DF2\u53D6\u6D88");
            setAllStepStatuses(state2, "\u5DF2\u53D6\u6D88", true);
          } else if (!state2.codeRunHasFinal) {
            finishCodeRun(state2, "\u2705 \u6267\u884C\u7ED3\u675F\uFF08\u65E0\u6700\u7EC8\u8F93\u51FA\uFF09");
          } else {
            finishCodeRun(state2, "\u2705 \u6267\u884C\u5B8C\u6210");
          }
          state2.currentSources = null;
          break;
        case "codeCancelRequested":
          state2.cancelRequested = true;
          updateCodeStatus(state2, "\u53D6\u6D88\u4E2D\u2026");
          setStopButtonState(true, "\u53D6\u6D88\u4E2D");
          setAllStepStatuses(state2, "\u53D6\u6D88\u4E2D", true);
          break;
        case "codeCancelled":
          state2.cancelRequested = true;
          finishCodeRun(state2, "\u{1F6D1} \u5DF2\u53D6\u6D88");
          setStopButtonState(true, "\u5DF2\u53D6\u6D88");
          addMilestone("\u4EFB\u52A1\u5DF2\u53D6\u6D88", "success", getActiveMilestoneContainer(state2));
          setAllStepStatuses(state2, "\u5DF2\u53D6\u6D88", true);
          state2.currentSources = null;
          break;
        case "error":
          if (state2.currentAssistantMsg) {
            state2.currentAssistantMsg.querySelector(".message-content").innerHTML = '<div class="error">\u274C ' + message.message + "</div>";
          }
          state2.codeRunHasFinal = true;
          finishCodeRun(state2, "\u274C \u6267\u884C\u5931\u8D25");
          state2.currentSources = null;
          break;
      }
    });
  }
  function sendMessage(state2, vscode2) {
    const input = document.getElementById("main-input");
    const text = input.value.trim();
    if (!text)
      return;
    addUserMessage(state2, text, vscode2);
    state2.currentAssistantMsg = addAssistantMessage(state2);
    switch (state2.currentMode) {
      case "ask":
        vscode2.postMessage({ command: "ask", query: text });
        break;
      case "agent":
        vscode2.postMessage({ command: "plan", task: text });
        break;
    }
    input.value = "";
  }
  function addUserMessage(state2, text, vscode2) {
    document.getElementById("welcome")?.classList.add("hidden");
    const container = document.getElementById("chat-container");
    const msg = document.createElement("div");
    msg.className = "message message-user";
    msg.dataset.originalText = text;
    msg.innerHTML = '<div class="message-content">' + escapeHtml(text) + "</div>";
    const content = msg.querySelector(".message-content");
    content.onclick = () => enterEditMode(state2, msg, vscode2);
    container.appendChild(msg);
    scrollToBottom();
  }
  function enterEditMode(state2, msg, vscode2) {
    const content = msg.querySelector(".message-content");
    if (content.classList.contains("editing"))
      return;
    const originalText = msg.dataset.originalText || "";
    content.classList.add("editing");
    content.innerHTML = `
        <textarea class="edit-textarea">${escapeHtml(originalText)}</textarea>
        <div class="edit-actions">
            <button class="edit-cancel">\u53D6\u6D88</button>
            <button class="edit-send">\u53D1\u9001</button>
        </div>
    `;
    const textarea = content.querySelector(".edit-textarea");
    textarea.focus();
    textarea.selectionStart = textarea.value.length;
    textarea.style.height = "auto";
    textarea.style.height = textarea.scrollHeight + "px";
    textarea.oninput = () => {
      textarea.style.height = "auto";
      textarea.style.height = textarea.scrollHeight + "px";
    };
    content.querySelector(".edit-cancel").onclick = (e) => {
      e.stopPropagation();
      exitEditMode(msg);
    };
    content.querySelector(".edit-send").onclick = (e) => {
      e.stopPropagation();
      const newText = textarea.value.trim();
      if (newText) {
        resendFromMessage(state2, msg, newText, vscode2);
      }
    };
    textarea.onkeydown = (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        const newText = textarea.value.trim();
        if (newText) {
          resendFromMessage(state2, msg, newText, vscode2);
        }
      }
      if (e.key === "Escape") {
        exitEditMode(msg);
      }
    };
    textarea.onclick = (e) => e.stopPropagation();
  }
  function exitEditMode(msg) {
    const content = msg.querySelector(".message-content");
    content.classList.remove("editing");
    content.innerHTML = escapeHtml(msg.dataset.originalText || "");
    content.onclick = () => {
    };
  }
  function resendFromMessage(state2, msg, newText, vscode2) {
    const container = document.getElementById("chat-container");
    let sibling = msg.nextElementSibling;
    while (sibling) {
      const next = sibling.nextElementSibling;
      container.removeChild(sibling);
      sibling = next;
    }
    msg.dataset.originalText = newText;
    const content = msg.querySelector(".message-content");
    content.classList.remove("editing");
    content.innerHTML = escapeHtml(newText);
    content.onclick = () => enterEditMode(state2, msg, vscode2);
    state2.currentAssistantMsg = addAssistantMessage(state2);
    state2.currentSources = null;
    switch (state2.currentMode) {
      case "ask":
        vscode2.postMessage({ command: "ask", query: newText });
        break;
      case "agent":
        vscode2.postMessage({ command: "plan", task: newText });
        break;
    }
  }
  function startCodeRun(state2) {
    state2.codeRunActive = true;
    state2.cancelRequested = false;
    state2.codeRunHasFinal = false;
    state2.lastActionMilestone = null;
    state2.activeStepIndex = null;
    state2.stepEventContainers = {};
    state2.stepMilestoneContainers = {};
    state2.stepStatusLabels = {};
    if (state2.currentAssistantMsg) {
      initCodeRunView(state2, state2.currentAssistantMsg);
    }
    state2.codeRunStart = Date.now();
    updateCodeStatus(state2, "\u6267\u884C\u4E2D \xB7 \u5DF2\u8FD0\u884C 0s");
    setStopButtonState(false, "\u505C\u6B62\u6267\u884C");
    if (state2.codeRunTimer) {
      clearInterval(state2.codeRunTimer);
    }
    state2.codeRunTimer = window.setInterval(() => {
      if (!state2.codeRunActive)
        return;
      const elapsed = formatElapsed(Date.now() - state2.codeRunStart);
      updateCodeStatus(state2, "\u6267\u884C\u4E2D \xB7 \u5DF2\u8FD0\u884C " + elapsed);
    }, 1e3);
  }
  function finishCodeRun(state2, statusText) {
    state2.codeRunActive = false;
    if (state2.codeRunTimer) {
      clearInterval(state2.codeRunTimer);
      state2.codeRunTimer = null;
    }
    if (statusText) {
      updateCodeStatus(state2, statusText);
    }
    setStopButtonState(true);
  }
  function requestCancel(state2, vscode2) {
    if (state2.cancelRequested)
      return;
    state2.cancelRequested = true;
    updateCodeStatus(state2, "\u53D6\u6D88\u4E2D\u2026");
    setStopButtonState(true, "\u53D6\u6D88\u4E2D");
    vscode2.postMessage({ command: "cancelCode" });
  }
  function isFailureObservation(content) {
    if (!content)
      return false;
    const sanitized = content.replace(/ERROR:\s+QEMU System Power off: with GPIO\./gi, "");
    return /失败|error|异常/i.test(sanitized);
  }
  function formatActionLabel(tool, input) {
    if (tool === "file_write") {
      return "\u5199\u5165\u6587\u4EF6 " + (input?.path || "");
    }
    if (tool === "file_read") {
      return "\u8BFB\u53D6\u6587\u4EF6 " + (input?.path || "");
    }
    if (tool === "ta_generator") {
      return "\u751F\u6210 TA " + (input?.name || "");
    }
    if (tool === "ca_generator") {
      return "\u751F\u6210 CA " + (input?.name || "");
    }
    if (tool === "crypto_helper") {
      return "\u751F\u6210\u52A0\u5BC6\u7247\u6BB5 " + (input?.operation || "");
    }
    return "\u6267\u884C\u5DE5\u5177 " + tool;
  }
  function setupDropdown(dropdownId, menuId, onSelect) {
    const dropdown = document.getElementById(dropdownId);
    const menu = document.getElementById(menuId);
    dropdown.querySelector(".selector").addEventListener("click", (e) => {
      e.stopPropagation();
      document.querySelectorAll(".dropdown-menu").forEach((m) => m !== menu && m.classList.remove("show"));
      menu.classList.toggle("show");
    });
    menu.querySelectorAll(".dropdown-item").forEach((item) => {
      item.onclick = () => {
        menu.querySelectorAll(".dropdown-item").forEach((i) => i.classList.remove("active"));
        item.classList.add("active");
        menu.classList.remove("show");
        onSelect(item);
      };
    });
  }

  // webview/mainView.ts
  var vscode = acquireVsCodeApi();
  var state = createState();
  bindDomEvents(state, vscode);
  bindMessageEvents(state, vscode);
})();
