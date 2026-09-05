/**
 * INTERNSPHERE — Client-Side Application Core
 * AI-Powered Internship Matching & Career Assistant
 */

(function () {
  'use strict';

  // State
  let currentUser = null;
  let userProfile = null;
  let currentResumes = [];
  let currentMatches = [];
  let allInternships = [];
  let currentApplications = [];
  let savedLettersList = [];
  let activeLetterRecord = null;
  let chatSessionsList = [];
  let currentChatSessionId = null;
  let selectedSkillGapInternshipId = null;
  let pendingModalAction = null;
  let selectedPhotoFile = null;

  // DOM Helpers
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  const escapeHtml = (str) => {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/'/g, '&#39;')
      .replace(/"/g, '&quot;');
  };

  // Toast System
  function showToast(message, isError = false) {
    const toast = $('#toast');
    toast.textContent = message;
    toast.style.borderColor = isError ? 'var(--danger)' : 'var(--accent-primary)';
    toast.classList.add('show');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove('show'), 3500);
  }

  // Modal Dialog System
  function showConfirmModal(title, message, onConfirm) {
    $('#modal-title').textContent = title;
    $('#modal-message').textContent = message;
    pendingModalAction = onConfirm;
    $('#modal-overlay').hidden = false;
  }

  function hideConfirmModal() {
    $('#modal-overlay').hidden = true;
    pendingModalAction = null;
  }

  // Unified Authenticated API Client
  async function api(endpoint, options = {}) {
    const token = localStorage.getItem('token');
    const isFormData = options.body instanceof FormData;
    const headers = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    };

    let response;
    try {
      response = await fetch(endpoint, { ...options, headers });
    } catch (netErr) {
      throw new Error('Network error. Please check your connection.');
    }

    const contentType = response.headers.get('content-type') || '';
    let data = null;
    if (contentType.includes('application/json')) {
      try {
        data = await response.json();
      } catch (e) {
        data = null;
      }
    } else if (contentType.includes('text/plain')) {
      data = await response.text();
    }

    if (!response.ok) {
      if (response.status === 401) {
        localStorage.removeItem('token');
        currentUser = null;
        renderAppShell();
        showToast('Your session has expired. Please sign in again.', true);
      }
      const errorMsg = data?.error?.message || data?.detail || 'An unexpected error occurred.';
      throw new Error(errorMsg);
    }
    return data;
  }

  // Theme Management
  function initTheme() {
    const savedTheme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    applyTheme(savedTheme);
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const icon = theme === 'dark' ? '☼' : '☾';
    const label = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
    $$('.theme-icon').forEach(el => el.textContent = icon);
    $$('.theme-label').forEach(el => el.textContent = label);
    const mobileBtn = $('#mobile-theme-btn');
    if (mobileBtn) mobileBtn.textContent = icon;
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    applyTheme(current);
  }

  // Client-Side Router
  function getRoute() {
    const path = location.pathname.replace(/^\/+|\/+$/g, '');
    if (!path) return 'dashboard';
    const firstSegment = path.split('/')[0];
    const aliases = {
      'cover-letter': 'cover-letters',
      'ai-assistant': 'assistant',
    };
    return aliases[firstSegment] || firstSegment;
  }

  function navigate(url) {
    history.pushState({}, '', url);
    handleRouteChange();
  }

  // Primary Page Dispatcher
  async function handleRouteChange() {
    initTheme();
    const token = localStorage.getItem('token');
    const route = getRoute();

    if (!token) {
      // Unauthenticated view ONLY
      $('#auth-view').hidden = false;
      $('#app-view').hidden = true;
      const isRegister = route === 'register';
      $('#login-box').hidden = isRegister;
      $('#register-box').hidden = !isRegister;
      $('#tab-login').classList.toggle('active', !isRegister);
      $('#tab-register').classList.toggle('active', isRegister);
      if (!['login', 'register'].includes(route)) {
        history.replaceState({}, '', '/login');
      }
      return;
    }

    // Authenticated App Shell
    $('#auth-view').hidden = true;
    $('#app-view').hidden = false;

    // Fetch authenticated user if not loaded
    if (!currentUser) {
      try {
        currentUser = await api('/me');
        updateUserBadge();
      } catch (err) {
        return;
      }
    }

    const validPages = [
      'dashboard',
      'profile',
      'resumes',
      'matches',
      'skill-gap',
      'applications',
      'cover-letters',
      'assistant',
    ];
    const targetPage = validPages.includes(route) ? route : 'dashboard';
    if (targetPage !== route) {
      history.replaceState({}, '', `/${targetPage}`);
    }

    // Show ONLY target page view, strictly hide all others
    $$('.view-page').forEach((el) => {
      const isMatch = el.id === `${targetPage}-page`;
      el.hidden = !isMatch;
    });

    // Update active nav link
    $$('.sidebar-nav .nav-item').forEach((el) => {
      const active = el.dataset.route === targetPage;
      el.classList.toggle('active', active);
    });

    // Close mobile drawer on route change
    $('#app-sidebar').classList.remove('mobile-open');
    $('#sidebar-backdrop').classList.remove('active');

    // Page-specific initializers
    if (targetPage === 'dashboard') loadDashboardView();
    if (targetPage === 'profile') loadProfileView();
    if (targetPage === 'resumes') loadResumesView();
    if (targetPage === 'matches') loadMatchesView();
    if (targetPage === 'skill-gap') loadSkillGapView();
    if (targetPage === 'applications') loadApplicationsView();
    if (targetPage === 'cover-letters') loadCoverLettersView();
    if (targetPage === 'assistant') loadAssistantView();
  }

  function updateUserBadge() {
    if (!currentUser) return;
    const badgeName = $('#user-badge-name');
    const badgeEmail = $('#user-badge-email');
    const badgeAvatar = $('#user-badge-avatar');

    const name = userProfile?.full_name || currentUser.username;
    if (badgeName) badgeName.textContent = name;
    if (badgeEmail) badgeEmail.textContent = currentUser.email;

    const initials = name
      .split(' ')
      .map((w) => w[0])
      .slice(0, 2)
      .join('')
      .toUpperCase();

    if (badgeAvatar) {
      if (userProfile?.profile_picture_path) {
        const token = localStorage.getItem('token');
        badgeAvatar.innerHTML = `<img src="/profile/picture?token=${encodeURIComponent(token)}&t=${Date.now()}" alt="${escapeHtml(name)}">`;
      } else {
        badgeAvatar.textContent = initials || 'IS';
      }
    }
  }

  // ==============================================================
  // VIEW 1: DASHBOARD
  // ==============================================================
  async function loadDashboardView() {
    try {
      const [profileData, resumesData, appsData, lettersData] = await Promise.all([
        api('/profile').catch(() => null),
        api('/resume').catch(() => []),
        api('/applications').catch(() => []),
        api('/cover-letters').catch(() => []),
      ]);

      userProfile = profileData;
      currentResumes = resumesData;
      currentApplications = appsData;
      savedLettersList = lettersData;
      updateUserBadge();

      // Welcome Headline
      const welcomeName = userProfile?.full_name || currentUser?.username || '';
      $('#dash-welcome').textContent = welcomeName ? `Welcome back, ${welcomeName}` : 'Welcome back';

      // Profile Completion Calculation
      const checkedFields = ['full_name', 'phone', 'location', 'college', 'degree', 'bio', 'technical_skills'];
      let completedCount = 0;
      if (userProfile) {
        checkedFields.forEach((field) => {
          const val = userProfile[field];
          if (Array.isArray(val) ? val.length > 0 : !!val) completedCount++;
        });
        if (userProfile.profile_picture_path) completedCount++;
      }
      const totalFields = checkedFields.length + 1;
      const completionPct = Math.round((completedCount / totalFields) * 100);

      $('#dash-profile-pct').textContent = `${completionPct}%`;
      $('#dash-profile-bar').style.width = `${completionPct}%`;
      $('#dash-resume-count').textContent = currentResumes.length;
      $('#dash-applications-count').textContent = currentApplications.length;
      $('#dash-letters-count').textContent = savedLettersList.length;

      // Recommended Matches Preview
      try {
        const matchRes = await api('/internships/match', {
          method: 'POST',
          body: JSON.stringify({ top_k: 4 }),
        });
        currentMatches = matchRes.recommendations || [];
        $('#dash-matches-count').textContent = currentMatches.length;
        renderInternshipCards(currentMatches.slice(0, 4), '#dash-matches-preview');
      } catch (matchErr) {
        $('#dash-matches-count').textContent = '—';
        $('#dash-matches-preview').innerHTML = `
          <div class="card" style="grid-column: 1/-1; text-align: center; padding: 32px;">
            <p class="card-hint">Upload your resume or complete your profile to unlock personalized internship recommendations.</p>
            <a href="/resumes" class="btn btn-primary" data-link>Upload Resume</a>
          </div>`;
      }
    } catch (e) {
      showToast('Could not load dashboard information.', true);
    }
  }

  // ==============================================================
  // VIEW 2: MY PROFILE
  // ==============================================================
  async function loadProfileView() {
    try {
      userProfile = await api('/profile');
      updateUserBadge();

      // Populate form inputs
      const form = $('#profile-details-form');
      const textFields = ['full_name', 'phone', 'location', 'college', 'degree', 'branch', 'graduation_year', 'cgpa', 'bio', 'linkedin', 'github', 'portfolio'];
      textFields.forEach((field) => {
        const input = form.querySelector(`[name="${field}"]`);
        if (input) input.value = userProfile[field] ?? '';
      });

      if ($('#prof-email')) $('#prof-email').value = currentUser?.email || '';

      const techSkills = [...(userProfile.technical_skills || []), ...(userProfile.skills || [])];
      if ($('#prof-tech-skills')) $('#prof-tech-skills').value = Array.from(new Set(techSkills)).join(', ');
      if ($('#prof-soft-skills')) $('#prof-soft-skills').value = (userProfile.soft_skills || []).join(', ');
      if ($('#prof-certifications')) {
        const certs = (userProfile.certifications || []).map((c) => (typeof c === 'string' ? c : c.name || '')).filter(Boolean);
        $('#prof-certifications').value = certs.join(', ');
      }
      if ($('#prof-achievements')) {
        const ach = (userProfile.achievements || []).map((a) => (typeof a === 'string' ? a : a.name || '')).filter(Boolean);
        $('#prof-achievements').value = ach.join(', ');
      }

      // Live skills tag cloud
      const allSkills = Array.from(new Set([...techSkills, ...(userProfile.soft_skills || [])]));
      const skillsContainer = $('#profile-skills-tags');
      if (allSkills.length > 0) {
        skillsContainer.innerHTML = allSkills.map((s) => `<span class="skill-tag">${escapeHtml(s)}</span>`).join('');
      } else {
        skillsContainer.innerHTML = '<span class="text-muted-sm">No skills added yet.</span>';
      }

      // Profile Photo Display
      renderProfilePhotoDisplay();
    } catch (err) {
      showToast('Could not load profile details.', true);
    }
  }

  function renderProfilePhotoDisplay() {
    const previewImg = $('#profile-picture-preview');
    const fallback = $('#profile-initials-fallback');
    const removeBtn = $('#profile-photo-remove-btn');
    const uploadBtn = $('#profile-photo-upload-btn');
    uploadBtn.disabled = true;

    const name = userProfile?.full_name || currentUser?.username || 'IS';
    const initials = name
      .split(' ')
      .map((w) => w[0])
      .slice(0, 2)
      .join('')
      .toUpperCase();
    fallback.textContent = initials;

    if (userProfile?.profile_picture_path) {
      const token = localStorage.getItem('token');
      previewImg.src = `/profile/picture?token=${encodeURIComponent(token)}&t=${Date.now()}`;
      previewImg.hidden = false;
      fallback.hidden = true;
      removeBtn.hidden = false;
    } else {
      previewImg.hidden = true;
      fallback.hidden = false;
      removeBtn.hidden = true;
    }
  }

  // ==============================================================
  // VIEW 3: MY RESUMES
  // ==============================================================
  async function loadResumesView() {
    try {
      currentResumes = await api('/resume');
      renderResumesList(currentResumes);
      if (currentResumes.length > 0) {
        renderParsedResumeAnalysis(currentResumes[0].parsed_json);
      } else {
        $('#resume-analysis-container').hidden = true;
      }
    } catch (err) {
      showToast('Failed to load resume documents.', true);
    }
  }

  function renderResumesList(resumes) {
    const container = $('#resumes-list-container');
    if (!resumes || resumes.length === 0) {
      container.innerHTML = '<p class="card-hint">No resumes uploaded yet. Upload your PDF or DOCX file to get started.</p>';
      return;
    }
    container.innerHTML = resumes
      .map(
        (r) => `
      <div class="resume-row">
        <div class="resume-info">
          <strong>${escapeHtml(r.original_filename)}</strong>
          <small>Uploaded on ${new Date(r.uploaded_at).toLocaleDateString()}</small>
        </div>
        <div class="resume-row-actions">
          <button class="btn btn-secondary btn-sm" data-action="view-parsed" data-id="${r.id}">View Analysis</button>
          <button class="btn btn-secondary btn-sm" data-action="reparse" data-id="${r.id}">Re-parse</button>
          <a class="btn btn-secondary btn-sm" href="/resume/${r.id}/download" target="_blank">Download</a>
        </div>
      </div>`
      )
      .join('');
  }

  // Beautiful Structured Resume Presentation (NO RAW JSON)
  function renderParsedResumeAnalysis(data) {
    if (!data) return;
    const container = $('#resume-analysis-container');
    container.hidden = false;

    // Name & Contact
    $('#parsed-candidate-name').textContent = data.full_name || userProfile?.full_name || 'Candidate';
    const chips = [];
    if (data.email) chips.push(`✉ ${escapeHtml(data.email)}`);
    if (data.phone) chips.push(`✆ ${escapeHtml(data.phone)}`);
    if (data.location) chips.push(`⚲ ${escapeHtml(data.location)}`);
    if (data.linkedin) chips.push(`in ${escapeHtml(data.linkedin)}`);
    if (data.github) chips.push(`git ${escapeHtml(data.github)}`);

    $('#parsed-contact-chips').innerHTML = chips.map((c) => `<span class="contact-chip">${c}</span>`).join('');

    // Summary
    $('#parsed-summary').textContent = data.professional_summary || 'No summary extracted from document.';

    // Skills
    const techSkills = data.technical_skills || [];
    const softSkills = data.soft_skills || [];
    $('#parsed-tech-skills').innerHTML = techSkills.length ? techSkills.map((s) => `<span class="skill-tag">${escapeHtml(s)}</span>`).join('') : '<span class="text-muted-sm">None listed</span>';
    $('#parsed-soft-skills').innerHTML = softSkills.length ? softSkills.map((s) => `<span class="skill-tag">${escapeHtml(s)}</span>`).join('') : '<span class="text-muted-sm">None listed</span>';

    // Experience
    const experiences = [...(data.work_experience || []), ...(data.internships || [])];
    const expContainer = $('#parsed-experience-list');
    if (experiences.length > 0) {
      expContainer.innerHTML = experiences
        .map(
          (e) => `
        <div class="timeline-card">
          <div class="timeline-title-row">
            <strong>${escapeHtml(e.title || 'Role')} · ${escapeHtml(e.company || 'Company')}</strong>
            <span>${escapeHtml(e.start_date || '')} – ${escapeHtml(e.end_date || 'Present')}</span>
          </div>
          ${e.location ? `<small class="meta-line">${escapeHtml(e.location)}</small>` : ''}
          ${Array.isArray(e.responsibilities) && e.responsibilities.length ? `<ul class="timeline-bullets">${e.responsibilities.map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>` : ''}
        </div>`
        )
        .join('');
    } else {
      expContainer.innerHTML = '<p class="text-muted-sm">No experience records detected.</p>';
    }

    // Projects
    const projects = data.projects || [];
    const projContainer = $('#parsed-projects-list');
    if (projects.length > 0) {
      projContainer.innerHTML = projects
        .map(
          (p) => `
        <div class="project-box">
          <h4>${escapeHtml(p.name || 'Project')}</h4>
          <p>${escapeHtml(p.description || '')}</p>
          <div class="tag-cloud">
            ${(p.technologies || []).map((t) => `<span class="badge badge-purple">${escapeHtml(t)}</span>`).join('')}
          </div>
        </div>`
        )
        .join('');
    } else {
      projContainer.innerHTML = '<p class="text-muted-sm">No projects listed.</p>';
    }

    // Education
    const education = data.education || [];
    const eduContainer = $('#parsed-education-list');
    if (education.length > 0) {
      eduContainer.innerHTML = education
        .map(
          (edu) => `
        <div class="edu-box">
          <strong>${escapeHtml(edu.degree || 'Degree')} ${edu.field_of_study ? `in ${escapeHtml(edu.field_of_study)}` : ''}</strong>
          <span>${escapeHtml(edu.institution || 'University')}</span>
          <small class="meta-line">${escapeHtml(edu.grade ? `CGPA/Grade: ${edu.grade}` : '')} · ${escapeHtml(edu.end_date || edu.start_date || '')}</small>
        </div>`
        )
        .join('');
    } else {
      eduContainer.innerHTML = '<p class="text-muted-sm">No education records detected.</p>';
    }

    // Certifications & Achievements
    const certs = data.certifications || [];
    $('#parsed-certifications-list').innerHTML = certs.length
      ? certs.map((c) => `<li><strong>${escapeHtml(c.name || '')}</strong> ${c.issuer ? `— ${escapeHtml(c.issuer)}` : ''}</li>`).join('')
      : '<li>None extracted</li>';

    const achs = data.achievements || [];
    $('#parsed-achievements-list').innerHTML = achs.length ? achs.map((a) => `<li>${escapeHtml(a)}</li>`).join('') : '<li>None extracted</li>';
  }

  // ==============================================================
  // VIEW 4: MATCHES & INTERNSHIP CARDS (BUG 1 FIX)
  // ==============================================================
  async function loadMatchesView() {
    const container = $('#matches-cards-container');
    container.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <span>Running RAG semantic search and skill verification...</span>
      </div>`;
    try {
      const matchRes = await api('/internships/match', {
        method: 'POST',
        body: JSON.stringify({ top_k: 10 }),
      });
      currentMatches = matchRes.recommendations || [];
      renderInternshipCards(currentMatches, '#matches-cards-container');
    } catch (err) {
      container.innerHTML = `
        <div class="card" style="grid-column: 1/-1; text-align: center; padding: 40px;">
          <h3 style="margin-bottom: 8px;">Resume or Profile Required</h3>
          <p class="card-hint">Please upload a resume or fill out your skills in My Profile before generating internship matches.</p>
          <a href="/resumes" class="btn btn-primary" data-link>Upload Resume Now</a>
        </div>`;
    }
  }

  function renderInternshipCards(internships, containerSelector) {
    const container = $(containerSelector);
    if (!internships || internships.length === 0) {
      container.innerHTML = '<p class="card-hint" style="grid-column:1/-1;">No internships matched your profile yet.</p>';
      return;
    }

    const appliedIds = new Set(currentApplications.map((a) => a.internship_id));

    container.innerHTML = internships
      .map((item) => {
        const isApplied = appliedIds.has(item.internship_id);
        const overallScore = item.overall_match_percentage ?? item.match_score ?? 0;
        const semanticScore = item.semantic_similarity ?? 0;
        const skillScore = item.skill_match_percentage ?? 0;

        const matchingSkills = item.matching_skills || [];
        const missingSkills = item.missing_skills || [];

        return `
        <article class="internship-card" data-id="${escapeHtml(item.internship_id)}">
          <div class="card-company-bar">
            <div class="company-avatar-group">
              <div class="company-badge-icon">${escapeHtml((item.company || 'IS')[0])}</div>
              <span class="company-name">${escapeHtml(item.company)}</span>
            </div>
            <div class="match-pct-badge ${overallScore >= 80 ? 'high' : ''}">
              <span>${overallScore}%</span> Match
            </div>
          </div>

          <h3>${escapeHtml(item.title)}</h3>

          <div class="card-meta-row">
            <span class="card-meta-item">⚲ ${escapeHtml(item.location || 'India')}</span>
            <span>•</span>
            <span class="card-meta-item">⏱ ${escapeHtml(item.work_mode || 'Hybrid')}</span>
            <span>•</span>
            <span class="card-meta-item">📅 ${escapeHtml(item.duration || '6 months')}</span>
          </div>

          <p class="card-description">${escapeHtml(item.description)}</p>

          <div class="match-submetrics">
            <span>Semantic: <strong>${semanticScore}%</strong></span>
            <span>Skill Match: <strong>${skillScore}%</strong></span>
          </div>

          <div class="card-skills-section">
            <div class="card-skills-label">Skill Coverage</div>
            <div class="tag-cloud">
              ${matchingSkills.slice(0, 4).map((s) => `<span class="skill-tag matched">✓ ${escapeHtml(s)}</span>`).join('')}
              ${missingSkills.slice(0, 3).map((s) => `<span class="skill-tag missing">✕ ${escapeHtml(s)}</span>`).join('')}
            </div>
          </div>

          <div class="card-action-bar">
            <button class="btn btn-secondary btn-sm" data-action="view-details" data-id="${item.internship_id}">View Details</button>
            <button class="btn btn-secondary btn-sm" data-action="goto-skillgap" data-id="${item.internship_id}">Skill Gap</button>
            <button class="btn btn-secondary btn-sm" data-action="goto-letter" data-id="${item.internship_id}">Cover Letter</button>
            <button class="btn ${isApplied ? 'btn-secondary' : 'btn-primary'} btn-sm" data-action="apply" data-id="${item.internship_id}" ${isApplied ? 'disabled' : ''}>
              ${isApplied ? 'Applied ✓' : 'Apply Now'}
            </button>
          </div>
        </article>`;
      })
      .join('');
  }

  // ==============================================================
  // VIEW 5: SKILL GAP ANALYSIS (Req 13)
  // ==============================================================
  async function loadSkillGapView() {
    try {
      if (allInternships.length === 0) {
        allInternships = await api('/internships');
      }
      const select = $('#skill-gap-select');
      select.innerHTML = '<option value="">Choose an internship listing...</option>' + allInternships.map((it) => `<option value="${it.internship_id}">${escapeHtml(it.title)} — ${escapeHtml(it.company)}</option>`).join('');

      if (selectedSkillGapInternshipId) {
        select.value = selectedSkillGapInternshipId;
        renderSelectedSkillGap(selectedSkillGapInternshipId);
      } else if (currentMatches.length > 0) {
        select.value = currentMatches[0].internship_id;
        renderSelectedSkillGap(currentMatches[0].internship_id);
      }
    } catch (err) {
      showToast('Could not load internship listings.', true);
    }
  }

  function renderSelectedSkillGap(internshipId) {
    if (!internshipId) {
      $('#skill-gap-details').hidden = true;
      return;
    }

    // Check if we have a match object for this internship
    let matchObj = currentMatches.find((m) => m.internship_id === internshipId);
    const internshipObj = allInternships.find((i) => i.internship_id === internshipId);

    if (!internshipObj) return;

    $('#skill-gap-details').hidden = false;
    $('#gap-company').textContent = internshipObj.company;
    $('#gap-role-title').textContent = internshipObj.title;
    $('#gap-location-meta').textContent = `${internshipObj.location || 'India'} · ${internshipObj.work_mode || 'Hybrid'} · ${internshipObj.duration || '6 months'}`;

    const overallPct = matchObj?.overall_match_percentage ?? 0;
    const skillPct = matchObj?.skill_match_percentage ?? 0;
    const semanticPct = matchObj?.semantic_similarity ?? 0;

    $('#gap-overall-pct').textContent = `${overallPct}%`;
    $('#gap-skill-pct').textContent = `${skillPct}%`;
    $('#gap-skill-bar').style.width = `${skillPct}%`;
    $('#gap-semantic-pct').textContent = `${semanticPct}%`;
    $('#gap-semantic-bar').style.width = `${semanticPct}%`;

    const matchedSkills = matchObj?.matching_skills || [];
    const missingSkills = matchObj?.missing_skills || internshipObj.required_skills || [];
    const missingPreferred = matchObj?.missing_preferred_skills || internshipObj.preferred_skills || [];

    $('#gap-matched-count').textContent = matchedSkills.length;
    $('#gap-matched-tags').innerHTML = matchedSkills.length
      ? matchedSkills.map((s) => `<span class="skill-tag matched">✓ ${escapeHtml(s)}</span>`).join('')
      : '<span class="text-muted-sm">No exact required/preferred skills matched yet.</span>';

    $('#gap-missing-count').textContent = missingSkills.length;
    $('#gap-missing-tags').innerHTML = missingSkills.length
      ? missingSkills.map((s) => `<span class="skill-tag missing">✕ ${escapeHtml(s)}</span>`).join('')
      : '<span class="text-muted-sm">None! You meet all mandatory skills.</span>';

    $('#gap-preferred-missing-count').textContent = missingPreferred.length;
    $('#gap-preferred-tags').innerHTML = missingPreferred.length
      ? missingPreferred.map((s) => `<span class="skill-tag preferred">○ ${escapeHtml(s)}</span>`).join('')
      : '<span class="text-muted-sm">None! You possess all preferred bonus skills.</span>';

    $('#gap-reason-text').textContent = matchObj?.reason || 'Calculated from your structured skills versus the internship requirement.';

    // Setup action buttons
    $('#gap-generate-letter-btn').onclick = () => {
      navigate('/cover-letters');
      $('#letter-target-internship').value = internshipId;
    };

    const isApplied = currentApplications.some((a) => a.internship_id === internshipId);
    const applyBtn = $('#gap-apply-btn');
    applyBtn.disabled = isApplied;
    applyBtn.textContent = isApplied ? 'Applied ✓' : 'Apply Now';
    applyBtn.onclick = async () => {
      if (isApplied) return;
      await submitApplication(internshipId);
      applyBtn.disabled = true;
      applyBtn.textContent = 'Applied ✓';
    };
  }

  // ==============================================================
  // VIEW 6: APPLICATIONS & TRACKING
  // ==============================================================
  async function loadApplicationsView() {
    try {
      currentApplications = await api('/applications');
      renderApplicationsTable(currentApplications);
    } catch (err) {
      showToast('Could not load applications.', true);
    }
  }

  function renderApplicationsTable(apps) {
    const container = $('#applications-container');
    if (!apps || apps.length === 0) {
      container.innerHTML = '<p class="card-hint" style="padding: 20px;">You have not applied to any internships yet. Check your Matches to apply.</p>';
      return;
    }

    container.innerHTML = `
      <table class="app-table">
        <thead>
          <tr>
            <th>Internship</th>
            <th>Applied Date</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${apps
            .map(
              (app) => `
            <tr>
              <td class="app-role-cell">
                <strong>${escapeHtml(app.internship_id)}</strong>
                <span>Application ID: #${app.id}</span>
              </td>
              <td>${new Date(app.applied_at).toLocaleDateString()}</td>
              <td>
                <span class="status-pill ${app.status.replace(/\s+/g, '')}">${escapeHtml(app.status)}</span>
              </td>
              <td>
                <div style="display: flex; gap: 8px;">
                  <button class="btn btn-secondary btn-sm" data-action="view-details" data-id="${app.internship_id}">View Role</button>
                  ${
                    !['Withdrawn', 'Accepted', 'Rejected', 'Selected'].includes(app.status)
                      ? `<button class="btn btn-danger-outline btn-sm" data-action="withdraw-app" data-id="${app.id}">Withdraw</button>`
                      : ''
                  }
                </div>
              </td>
            </tr>`
            )
            .join('')}
        </tbody>
      </table>`;
  }

  // ==============================================================
  // VIEW 7: COVER LETTERS (BUG 4 & 5 FIX)
  // ==============================================================
  async function loadCoverLettersView() {
    try {
      const [letters, internships] = await Promise.all([
        api('/cover-letters'),
        allInternships.length ? allInternships : api('/internships'),
      ]);
      savedLettersList = letters;
      allInternships = internships;

      // Populate internship select
      const select = $('#letter-target-internship');
      select.innerHTML = '<option value="">Choose an internship...</option>' + allInternships.map((it) => `<option value="${it.internship_id}">${escapeHtml(it.title)} — ${escapeHtml(it.company)}</option>`).join('');

      renderSavedLetters(savedLettersList);
    } catch (err) {
      showToast('Could not load cover letter workspace.', true);
    }
  }

  function renderSavedLetters(letters) {
    const container = $('#saved-letters-container');
    if (!letters || letters.length === 0) {
      container.innerHTML = '<p class="card-hint">No saved cover letters. Choose an internship and generate one with Gemini.</p>';
      return;
    }
    container.innerHTML = letters
      .map(
        (letter) => `
      <div class="saved-letter-item">
        <div>
          <strong>${escapeHtml(letter.internship_id)}</strong>
          <small class="meta-line">Updated ${new Date(letter.updated_at).toLocaleDateString()}</small>
        </div>
        <button class="btn btn-secondary btn-sm" data-action="edit-letter" data-id="${letter.id}">Open Editor</button>
      </div>`
      )
      .join('');
  }

  function openLetterInEditor(letter) {
    activeLetterRecord = letter;
    const editorCard = $('#letter-editor-container');
    editorCard.hidden = false;
    $('#editing-letter-title').textContent = `Cover Letter — ${letter.internship_id}`;
    $('#letter-textarea').value = letter.content;
    $('#letter-save-status').textContent = '';
    editorCard.scrollIntoView({ behavior: 'smooth' });
  }

  // Pure Cover Letter File Downloads (BUG 4 FIX - ZERO PHOTO CONTENT)
  async function downloadCoverLetterFile(format = 'txt') {
    if (!activeLetterRecord) {
      showToast('Open or generate a cover letter first.', true);
      return;
    }
    const token = localStorage.getItem('token');
    const endpoint = format === 'pdf' ? `/cover-letters/${activeLetterRecord.id}/download-pdf?token=${encodeURIComponent(token)}` : `/cover-letters/${activeLetterRecord.id}/download?token=${encodeURIComponent(token)}`;

    try {
      showToast(`Downloading cover letter (${format.toUpperCase()})...`);
      const res = await fetch(endpoint, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Download request failed.');

      const blob = await res.blob();
      // Enforce clean plain text or application/pdf MIME type
      const verifiedBlob = new Blob([blob], { type: format === 'pdf' ? 'application/pdf' : 'text/plain;charset=utf-8' });
      const downloadUrl = window.URL.createObjectURL(verifiedBlob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `cover-letter-${activeLetterRecord.internship_id || activeLetterRecord.id}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(downloadUrl), 2000);
      showToast('Download complete.');
    } catch (e) {
      showToast('Could not download cover letter.', true);
    }
  }

  // ==============================================================
  // VIEW 8: AI ASSISTANT (BUG 10, 11, 12 FIX)
  // ==============================================================
  async function loadAssistantView() {
    try {
      chatSessionsList = await api('/assistant/sessions');
      renderChatSessions(chatSessionsList);

      if (currentChatSessionId) {
        // Load active session messages
        await loadSessionMessages(currentChatSessionId);
      } else if (chatSessionsList.length > 0) {
        // Default to most recent session
        currentChatSessionId = chatSessionsList[0].id;
        await loadSessionMessages(currentChatSessionId);
      } else {
        // Start fresh empty session
        await createNewChatSession();
      }
    } catch (err) {
      showToast('Could not load chat sessions.', true);
    }
  }

  function renderChatSessions(sessions) {
    const container = $('#chat-sessions-list');
    if (!sessions || sessions.length === 0) {
      container.innerHTML = '<p class="card-hint">No recent chats.</p>';
      return;
    }
    container.innerHTML = sessions
      .map(
        (s) => `
      <div class="session-item-btn ${s.id === currentChatSessionId ? 'active' : ''}" data-action="switch-session" data-id="${s.id}">
        <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;">${escapeHtml(s.title)}</span>
        <button class="session-delete-btn" data-action="delete-session" data-id="${s.id}" title="Delete chat">&times;</button>
      </div>`
      )
      .join('');
  }

  async function createNewChatSession() {
    try {
      const newSession = await api('/assistant/sessions', {
        method: 'POST',
        body: JSON.stringify({ title: 'New Career Chat' }),
      });
      currentChatSessionId = newSession.id;
      chatSessionsList = [newSession, ...chatSessionsList];
      renderChatSessions(chatSessionsList);

      // Reset message view to empty welcome state (BUG 10 FIX)
      $('#active-chat-title').textContent = newSession.title;
      renderWelcomeChatState();
    } catch (err) {
      showToast('Could not initialize new chat session.', true);
    }
  }

  function renderWelcomeChatState() {
    const container = $('#chat-messages-container');
    container.innerHTML = `
      <div class="chat-welcome-state">
        <div class="cw-icon">◌</div>
        <h3>Welcome to InternSphere AI</h3>
        <p>Ask anything about matching, your skill gaps, resume extraction, or applications.</p>
        <div class="suggestion-chips">
          <button class="suggest-chip" type="button">How does internship matching work?</button>
          <button class="suggest-chip" type="button">What is skill gap analysis?</button>
          <button class="suggest-chip" type="button">How does resume parsing work?</button>
          <button class="suggest-chip" type="button">What does my match percentage mean?</button>
        </div>
      </div>`;
  }

  async function loadSessionMessages(sessionId) {
    currentChatSessionId = sessionId;
    const session = chatSessionsList.find((s) => s.id === sessionId);
    $('#active-chat-title').textContent = session?.title || 'Conversation';
    renderChatSessions(chatSessionsList);

    const container = $('#chat-messages-container');
    container.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <span>Loading session messages...</span>
      </div>`;

    try {
      const messages = await api(`/assistant/sessions/${sessionId}`);
      if (!messages || messages.length === 0) {
        renderWelcomeChatState();
      } else {
        container.innerHTML = messages.map((m) => renderMessageBubbleHtml(m.role, m.content)).join('');
        container.scrollTop = container.scrollHeight;
      }
    } catch (e) {
      renderWelcomeChatState();
    }
  }

  function renderMessageBubbleHtml(role, content, sources = []) {
    const isUser = role === 'user';
    const avatar = isUser ? (currentUser?.username?.[0] || 'U').toUpperCase() : 'IS';
    const sourcesHtml = sources && sources.length ? `<span class="chat-sources-tag">Sources: ${escapeHtml(sources.join(', '))}</span>` : '';

    return `
      <div class="chat-bubble-row ${isUser ? 'user' : 'assistant'}">
        <div class="chat-bubble-avatar">${avatar}</div>
        <div class="chat-bubble">
          <div>${escapeHtml(content).replace(/\n/g, '<br>')}</div>
          ${sourcesHtml}
        </div>
      </div>`;
  }

  async function sendAssistantMessage(question) {
    if (!question || !question.trim()) return;
    const container = $('#chat-messages-container');

    // Remove welcome state if present
    const welcome = container.querySelector('.chat-welcome-state');
    if (welcome) welcome.remove();

    // Append user message immediately
    container.insertAdjacentHTML('beforeend', renderMessageBubbleHtml('user', question));
    container.scrollTop = container.scrollHeight;

    // Show typing placeholder
    const typingId = 'typing-' + Date.now();
    container.insertAdjacentHTML(
      'beforeend',
      `
      <div id="${typingId}" class="chat-bubble-row assistant">
        <div class="chat-bubble-avatar">IS</div>
        <div class="chat-bubble"><div class="spinner" style="width:16px; height:16px; border-width:2px;"></div></div>
      </div>`
    );
    container.scrollTop = container.scrollHeight;

    try {
      const res = await api('/assistant/chat', {
        method: 'POST',
        body: JSON.stringify({ question, session_id: currentChatSessionId }),
      });

      const typingEl = $(`#${typingId}`);
      if (typingEl) typingEl.remove();

      container.insertAdjacentHTML('beforeend', renderMessageBubbleHtml('assistant', res.answer, res.sources));
      container.scrollTop = container.scrollHeight;

      // Refresh chat title if updated
      const sIndex = chatSessionsList.findIndex((s) => s.id === currentChatSessionId);
      if (sIndex !== -1 && chatSessionsList[sIndex].title === 'New Career Chat') {
        chatSessionsList[sIndex].title = question.slice(0, 50);
        renderChatSessions(chatSessionsList);
        $('#active-chat-title').textContent = chatSessionsList[sIndex].title;
      }
    } catch (err) {
      const typingEl = $(`#${typingId}`);
      if (typingEl) typingEl.remove();
      container.insertAdjacentHTML('beforeend', renderMessageBubbleHtml('assistant', err.message || 'Sorry, I encountered an error answering your question.'));
    }
  }

  // Application Submission Helper
  async function submitApplication(internshipId) {
    try {
      showToast('Submitting your application...');
      await api('/applications', {
        method: 'POST',
        body: JSON.stringify({ internship_id: internshipId }),
      });
      showToast('Application submitted successfully!');
      currentApplications = await api('/applications');
      if (getRoute() === 'matches') loadMatchesView();
    } catch (err) {
      showToast(err.message, true);
    }
  }

  // Internship Detail Modal Helper
  async function openInternshipModal(internshipId) {
    try {
      const it = allInternships.find((i) => i.internship_id === internshipId) || (await api(`/internships/${internshipId}`));
      $('#im-company').textContent = it.company;
      $('#im-title').textContent = it.title;
      $('#im-meta').textContent = `${it.location || 'India'} · ${it.work_mode || 'Hybrid'} · ${it.duration || '6 months'} · ${it.stipend || 'Stipend available'}`;
      $('#im-description').textContent = it.description;

      $('#im-required-skills').innerHTML = (it.required_skills || []).map((s) => `<span class="skill-tag">${escapeHtml(s)}</span>`).join('');
      $('#im-preferred-skills').innerHTML = (it.preferred_skills || []).map((s) => `<span class="skill-tag preferred">${escapeHtml(s)}</span>`).join('');
      $('#im-education').textContent = it.education_requirements || it.eligibility || 'Degree in relevant discipline.';
      $('#im-experience').textContent = it.experience_requirements || 'Prior project or programming experience.';
      $('#im-deadline').textContent = it.application_deadline ? `Applications close: ${it.application_deadline}` : 'Open for early applicants';

      $('#im-skillgap-btn').onclick = () => {
        $('#internship-modal').hidden = true;
        selectedSkillGapInternshipId = internshipId;
        navigate('/skill-gap');
      };
      $('#im-letter-btn').onclick = () => {
        $('#internship-modal').hidden = true;
        navigate('/cover-letters');
        $('#letter-target-internship').value = internshipId;
      };

      const isApplied = currentApplications.some((a) => a.internship_id === internshipId);
      const applyBtn = $('#im-apply-btn');
      applyBtn.disabled = isApplied;
      applyBtn.textContent = isApplied ? 'Applied ✓' : 'Apply Now';
      applyBtn.onclick = async () => {
        await submitApplication(internshipId);
        applyBtn.disabled = true;
        applyBtn.textContent = 'Applied ✓';
      };

      $('#internship-modal').hidden = false;
    } catch (e) {
      showToast('Could not load internship details.', true);
    }
  }

  // ==============================================================
  // GLOBAL EVENT LISTENERS
  // ==============================================================
  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    handleRouteChange();
  });

  window.addEventListener('popstate', handleRouteChange);

  // Link delegation
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a[data-link]');
    if (link) {
      e.preventDefault();
      const href = link.getAttribute('href');
      navigate(href);
      return;
    }

    // Theme toggles
    if (e.target.closest('.theme-toggle-btn')) {
      toggleTheme();
      return;
    }

    // Sidebar collapse toggle
    if (e.target.closest('#sidebar-collapse-btn')) {
      $('#app-sidebar').classList.toggle('collapsed');
      return;
    }

    // Mobile navigation toggle
    if (e.target.closest('#mobile-menu-btn')) {
      $('#app-sidebar').classList.add('mobile-open');
      $('#sidebar-backdrop').classList.add('active');
      return;
    }
    if (e.target.closest('#sidebar-backdrop')) {
      $('#app-sidebar').classList.remove('mobile-open');
      $('#sidebar-backdrop').classList.remove('active');
      return;
    }

    // Modal close
    if (e.target.closest('#im-close-btn') || e.target.id === 'internship-modal') {
      $('#internship-modal').hidden = true;
      return;
    }
    if (e.target.closest('#modal-cancel-btn') || e.target.id === 'modal-overlay') {
      hideConfirmModal();
      return;
    }
    if (e.target.closest('#modal-confirm-btn')) {
      if (typeof pendingModalAction === 'function') pendingModalAction();
      hideConfirmModal();
      return;
    }

    // Auth Switch Tabs
    if (e.target.id === 'tab-login') navigate('/login');
    if (e.target.id === 'tab-register') navigate('/register');

    // Matches / Cards Action delegation
    const btn = e.target.closest('button[data-action]');
    if (btn) {
      const action = btn.dataset.action;
      const id = btn.dataset.id;

      if (action === 'apply') {
        submitApplication(id);
      } else if (action === 'view-details') {
        openInternshipModal(id);
      } else if (action === 'goto-skillgap') {
        selectedSkillGapInternshipId = id;
        navigate('/skill-gap');
      } else if (action === 'goto-letter') {
        navigate('/cover-letters');
        setTimeout(() => {
          const select = $('#letter-target-internship');
          if (select) select.value = id;
        }, 100);
      } else if (action === 'view-parsed') {
        const resObj = currentResumes.find((r) => r.id === Number(id));
        if (resObj) renderParsedResumeAnalysis(resObj.parsed_json);
      } else if (action === 'reparse') {
        showToast('Re-parsing resume with Gemini...');
        api(`/resume/${id}/reparse`, { method: 'POST' })
          .then((updated) => {
            showToast('Resume re-parsed successfully!');
            loadResumesView();
          })
          .catch((err) => showToast(err.message, true));
      } else if (action === 'withdraw-app') {
        showConfirmModal('Withdraw Application', 'Are you sure you want to withdraw this application? This action cannot be undone.', async () => {
          try {
            await api(`/applications/${id}/withdraw`, { method: 'POST' });
            showToast('Application withdrawn.');
            loadApplicationsView();
          } catch (err) {
            showToast(err.message, true);
          }
        });
      } else if (action === 'edit-letter') {
        const letter = savedLettersList.find((l) => l.id === Number(id));
        if (letter) openLetterInEditor(letter);
      } else if (action === 'switch-session') {
        loadSessionMessages(Number(id));
      } else if (action === 'delete-session') {
        showConfirmModal('Delete Chat Session', 'Are you sure you want to delete this chat session?', async () => {
          try {
            await api(`/assistant/sessions/${id}`, { method: 'DELETE' });
            chatSessionsList = chatSessionsList.filter((s) => s.id !== Number(id));
            if (currentChatSessionId === Number(id)) {
              currentChatSessionId = chatSessionsList[0]?.id || null;
            }
            loadAssistantView();
            showToast('Chat session deleted.');
          } catch (e) {
            showToast('Could not delete chat.', true);
          }
        });
      }
      return;
    }

    // Suggestion chips in Assistant
    if (e.target.classList.contains('suggest-chip')) {
      sendAssistantMessage(e.target.textContent);
      return;
    }
  });

  // Authentication Forms
  $('#login-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = $('#login-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Signing in...';
    try {
      const data = Object.fromEntries(new FormData(e.target));
      const res = await api('/login', { method: 'POST', body: JSON.stringify(data) });
      localStorage.setItem('token', res.access_token);
      currentUser = await api('/me');
      navigate('/dashboard');
      showToast('Welcome to InternSphere!');
    } catch (err) {
      showToast(err.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Sign In to InternSphere';
    }
  };

  $('#register-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = $('#register-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Creating account...';
    try {
      const data = Object.fromEntries(new FormData(e.target));
      await api('/register', { method: 'POST', body: JSON.stringify(data) });
      showToast('Account created successfully! Please sign in.');
      navigate('/login');
    } catch (err) {
      showToast(err.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Create Account';
    }
  };

  $('#logout-btn').onclick = async () => {
    try {
      await api('/logout', { method: 'POST' });
    } catch (e) {
      // Ignore
    }
    localStorage.removeItem('token');
    currentUser = null;
    userProfile = null;
    navigate('/login');
    showToast('Logged out successfully.');
  };

  // Profile Form & Picture Upload
  $('#profile-photo-choose-btn').onclick = () => {
    $('#profile-photo-input').click();
  };

  $('#profile-photo-input').onchange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    selectedPhotoFile = file;
    const reader = new FileReader();
    reader.onload = (re) => {
      const previewImg = $('#profile-picture-preview');
      previewImg.src = re.target.result;
      previewImg.hidden = false;
      $('#profile-initials-fallback').hidden = true;
      $('#profile-photo-upload-btn').disabled = false;
      $('#photo-upload-status').textContent = 'Photo selected. Click "Save Photo" to upload.';
    };
    reader.readAsDataURL(file);
  };

  $('#profile-photo-upload-btn').onclick = async () => {
    if (!selectedPhotoFile) return;
    const btn = $('#profile-photo-upload-btn');
    btn.disabled = true;
    btn.textContent = 'Uploading...';
    try {
      const fd = new FormData();
      fd.append('file', selectedPhotoFile);
      userProfile = await api('/profile/picture', { method: 'POST', body: fd });
      showToast('Profile photo updated successfully!');
      renderProfilePhotoDisplay();
      updateUserBadge();
      $('#photo-upload-status').textContent = 'Photo saved.';
    } catch (err) {
      showToast(err.message, true);
      $('#photo-upload-status').textContent = 'Upload failed.';
    } finally {
      btn.disabled = true;
      btn.textContent = 'Save Photo';
      selectedPhotoFile = null;
    }
  };

  $('#profile-photo-remove-btn').onclick = async () => {
    showConfirmModal('Remove Profile Picture', 'Are you sure you want to remove your profile photo?', async () => {
      try {
        userProfile = await api('/profile/picture', { method: 'DELETE' });
        showToast('Profile photo removed.');
        renderProfilePhotoDisplay();
        updateUserBadge();
      } catch (err) {
        showToast(err.message, true);
      }
    });
  };

  $('#profile-details-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = $('#profile-save-btn');
    btn.disabled = true;
    btn.textContent = 'Saving...';
    try {
      const raw = Object.fromEntries(new FormData(e.target));
      const payload = {
        full_name: raw.full_name || null,
        phone: raw.phone || null,
        location: raw.location || null,
        address: raw.location || null,
        college: raw.college || null,
        degree: raw.degree || null,
        branch: raw.branch || null,
        graduation_year: raw.graduation_year ? parseInt(raw.graduation_year, 10) : null,
        cgpa: raw.cgpa || null,
        bio: raw.bio || null,
        linkedin: raw.linkedin || null,
        github: raw.github || null,
        portfolio: raw.portfolio || null,
        technical_skills: (raw.technical_skills || '').split(',').map((s) => s.trim()).filter(Boolean),
        soft_skills: (raw.soft_skills || '').split(',').map((s) => s.trim()).filter(Boolean),
        certifications: (raw.certifications_input || '').split(',').map((s) => ({ name: s.trim() })).filter((c) => c.name),
        achievements: (raw.achievements_input || '').split(',').map((s) => s.trim()).filter(Boolean),
      };
      userProfile = await api('/profile', { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Profile details saved successfully!');
      loadProfileView();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Save Profile Changes';
    }
  };

  // Resume Upload Form
  $('#resume-file-input').onchange = (e) => {
    const file = e.target.files[0];
    const badge = $('#selected-file-name');
    if (file) {
      badge.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
      badge.hidden = false;
    } else {
      badge.hidden = true;
    }
  };

  $('#resume-upload-form').onsubmit = async (e) => {
    e.preventDefault();
    const btn = $('#resume-upload-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" style="width:16px;height:16px;border-width:2px;"></span> Parsing with AI...';

    try {
      const fd = new FormData(e.target);
      const newResume = await api('/resume/upload', { method: 'POST', body: fd });
      showToast('Resume uploaded and parsed successfully!');
      e.target.reset();
      $('#selected-file-name').hidden = true;
      await loadResumesView();
      renderParsedResumeAnalysis(newResume.parsed_json);
    } catch (err) {
      showToast(err.message || 'Resume parsing failed. Please try again.', true);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Upload & Parse with AI';
    }
  };

  // Refresh Matches
  $('#refresh-matches-btn').onclick = () => loadMatchesView();

  // Skill Gap Dropdown Change
  $('#skill-gap-select').onchange = (e) => {
    selectedSkillGapInternshipId = e.target.value;
    renderSelectedSkillGap(selectedSkillGapInternshipId);
  };

  // Cover Letter Generator
  $('#letter-generate-form').onsubmit = async (e) => {
    e.preventDefault();
    const internshipId = $('#letter-target-internship').value;
    if (!internshipId) return;

    const btn = $('#generate-letter-submit-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" style="width:16px;height:16px;border-width:2px;"></span> Generating with Gemini...';

    try {
      const letter = await api('/cover-letters/generate', {
        method: 'POST',
        body: JSON.stringify({ internship_id: internshipId }),
      });
      showToast('Cover letter generated with Gemini!');
      savedLettersList = [letter, ...savedLettersList];
      renderSavedLetters(savedLettersList);
      openLetterInEditor(letter);
    } catch (err) {
      showToast(err.message || 'AI generation failed. Please try again.', true);
    } finally {
      btn.disabled = false;
      btn.textContent = '✦ Generate with Gemini';
    }
  };

  // Cover Letter Editor Actions
  $('#letter-save-form').onsubmit = async (e) => {
    e.preventDefault();
    if (!activeLetterRecord) return;
    const content = $('#letter-textarea').value;
    try {
      activeLetterRecord = await api(`/cover-letters/${activeLetterRecord.id}`, {
        method: 'PUT',
        body: JSON.stringify({ content }),
      });
      $('#letter-save-status').textContent = 'Changes saved.';
      showToast('Cover letter updated successfully.');
      savedLettersList = await api('/cover-letters');
      renderSavedLetters(savedLettersList);
    } catch (err) {
      showToast(err.message, true);
    }
  };

  $('#editor-copy-btn').onclick = async () => {
    const text = $('#letter-textarea').value;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      showToast('Cover letter copied to clipboard!');
    } catch (e) {
      showToast('Failed to copy text.', true);
    }
  };

  $('#editor-regenerate-btn').onclick = async () => {
    if (!activeLetterRecord) return;
    showConfirmModal('Regenerate Cover Letter', 'Regenerate this cover letter with Gemini? Your current edits will be replaced.', async () => {
      try {
        showToast('Regenerating cover letter...');
        const newLetter = await api('/cover-letters/generate', {
          method: 'POST',
          body: JSON.stringify({ internship_id: activeLetterRecord.internship_id }),
        });
        showToast('Cover letter regenerated.');
        openLetterInEditor(newLetter);
      } catch (err) {
        showToast(err.message, true);
      }
    });
  };

  $('#editor-download-txt-btn').onclick = () => downloadCoverLetterFile('txt');
  $('#editor-download-pdf-btn').onclick = () => downloadCoverLetterFile('pdf');

  // AI Assistant Actions
  $('#new-chat-btn').onclick = () => createNewChatSession();

  $('#assistant-chat-form').onsubmit = (e) => {
    e.preventDefault();
    const input = $('#chat-input');
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    sendAssistantMessage(q);
  };
})();
