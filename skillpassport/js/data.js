// ===== MOCK DATA STORE (localStorage-backed) =====

const DEFAULT_DATA = {
    competencies: [
        { id: 1, code: 'SP1.C1', name: 'Cellular Analysis', description: 'Understanding microbial structures and laboratory identification techniques.', status: 'Active', stage: 'Foundational' },
        { id: 2, code: 'SP1.C2', name: 'Organic Synthesis', description: 'Advanced preparation of carbon-based molecules and functional groups.', status: 'Active', stage: 'Preparatory' },
        { id: 3, code: 'SP1.C3', name: 'Quantum Theory', description: 'Conceptual overview of particle physics and wave-particle duality.', status: 'Draft', stage: 'Middle' },
        { id: 4, code: 'SP1.C4', name: 'Data Visualization', description: 'Reporting complex data sets through graphical representations.', status: 'Active', stage: 'Secondary' },
    ],
    profiles: [
        { id: 1,  name: 'Tech Innovator',         primaryCompetencies: ['SP7.C3', 'SP13.C1'],  secondaryCompetencies: ['SP1.C2', 'SP5.C7'] },
        { id: 2,  name: 'Strategic Thinker',       primaryCompetencies: ['SP6.C4', 'SP2.C3'],  secondaryCompetencies: ['SP9.C1', 'SP3.C3'] },
        { id: 3,  name: 'Social Leader',           primaryCompetencies: ['SP3.C3', 'SP5.C6'],  secondaryCompetencies: ['SP13.C3', 'SP9.C1'] },
        { id: 4,  name: 'Financial Steward',       primaryCompetencies: ['SP10.C3', 'SP4.C5'], secondaryCompetencies: ['SP5.C7', 'SP13.C3'] },
        { id: 5,  name: 'Well-Being Navigator',    primaryCompetencies: ['SP9.C3', 'SP1.C1'],  secondaryCompetencies: ['SP13.C11', 'SP5.C6'] },
        { id: 6,  name: 'Creative Maker',          primaryCompetencies: ['SP8.C2', 'SP11.C2'], secondaryCompetencies: ['SP3.C2', 'SP6.C3'] },
        { id: 7,  name: 'Critical Analyst',        primaryCompetencies: ['SP2.C1', 'SP6.C2'],  secondaryCompetencies: ['SP4.C3', 'SP10.C1'] },
        { id: 8,  name: 'Global Communicator',     primaryCompetencies: ['SP3.C1', 'SP5.C3'],  secondaryCompetencies: ['SP2.C4', 'SP9.C2'] },
        { id: 9,  name: 'Environmental Champion',  primaryCompetencies: ['SP12.C2', 'SP4.C2'], secondaryCompetencies: ['SP3.C4', 'SP7.C1'] },
        { id: 10, name: 'Entrepreneurial Mind',    primaryCompetencies: ['SP10.C2', 'SP6.C1'], secondaryCompetencies: ['SP2.C5', 'SP7.C2'] },
        { id: 11, name: 'Research Scholar',        primaryCompetencies: ['SP4.C1', 'SP2.C2'],  secondaryCompetencies: ['SP6.C3', 'SP1.C3'] },
        { id: 12, name: 'Digital Navigator',       primaryCompetencies: ['SP13.C2', 'SP7.C4'], secondaryCompetencies: ['SP10.C4', 'SP5.C1'] },
        { id: 13, name: 'Community Builder',       primaryCompetencies: ['SP5.C4', 'SP3.C5'],  secondaryCompetencies: ['SP9.C4', 'SP1.C4'] },
        { id: 14, name: 'Design Thinker',          primaryCompetencies: ['SP11.C1', 'SP8.C1'], secondaryCompetencies: ['SP6.C5', 'SP2.C6'] },
        { id: 15, name: 'Collaborative Leader',    primaryCompetencies: ['SP5.C5', 'SP9.C5'],  secondaryCompetencies: ['SP3.C6', 'SP13.C4'] },
    ],
    projects: {
        grade: 'Grade 10',
        title: 'Sustainable Urban Development Capstone',
        type: 'Capstone',
        assessments: [
            { id: 1, name: 'Initial Proposal & Literature Review', type: 'Written Assignment', expanded: true },
            { id: 2, name: 'Data Collection & Methodology', type: 'Lab Report', expanded: false },
            { id: 3, name: 'Mid-Project Progress Review', type: 'Presentation', expanded: false },
            { id: 4, name: 'Final Draft Submission', type: 'Written Assignment', expanded: false },
            { id: 5, name: 'Oral Defense & Presentation', type: 'Presentation', expanded: false },
            { id: 6, name: 'Self-Reflection & Portfolio Entry', type: 'Written Assignment', expanded: false },
        ]
    },
    students: [
        { id: 1, name: 'Alex Johnson', initials: 'AJ', color: 'primary', scores: [8, 9, null, 7, null] },
        { id: 2, name: 'Maria Garcia', initials: 'MG', color: 'blue', scores: [10, 10, 9, 10, 9] },
        { id: 3, name: 'Liam Smith', initials: 'LS', color: 'purple', scores: [null, null, null, null, null] },
        { id: 4, name: 'Chloe Chen', initials: 'CC', color: 'orange', scores: [8, 8, 7, 9, 8] },
        { id: 5, name: 'Jordan Taylor', initials: 'JT', color: 'emerald', scores: [9, null, 8, 9, 7] },
    ],
    selectedStudent: null,
    studentScoring: {
        name: 'Alexander Thompson',
        competencies: [
            { name: 'Critical Thinking', description: 'Analyze information, synthesize data, and draw objective conclusions.', level: '', stage: 'Middle' },
            { name: 'Digital Literacy', description: 'Proficiency in using digital tools and platforms for academic research.', level: '', stage: 'Foundational' },
            { name: 'Communication', description: 'Effectiveness in verbal and written articulation of complex ideas.', level: '3', stage: 'Foundational' },
            { name: 'Collaborative Leadership', description: 'Ability to guide a team while maintaining positive interpersonal dynamics.', level: '', stage: 'Secondary' },
        ],
        feedback: '',
    },
    analytics: {
        studentName: 'Alexander Smith',
        grade: 'Grade 10 - Section B',
        studentId: '#ST-98231',
        avgLevel: 3.2,
        attendance: 94,
        competencies: [
            { name: 'Problem Solving', icon: 'psychology', score: 3.2, width: 80 },
            { name: 'Critical Thinking', icon: 'lightbulb', score: 2.4, width: 60 },
            { name: 'Communication', icon: 'chat', score: 3.8, width: 95 },
            { name: 'Collaboration', icon: 'group_add', score: 3.5, width: 88 },
        ]
    }
};

function loadData() {
    const stored = localStorage.getItem('skillPassportData');
    if (stored) {
        const parsed = JSON.parse(stored);
        // Reset if competency codes are in old format (e.g. BIO-101) or profiles is not an array
        if ((parsed.competencies && parsed.competencies[0] && !parsed.competencies[0].code.startsWith('SP')) ||
            !Array.isArray(parsed.profiles)) {
            saveData(DEFAULT_DATA);
            return { ...DEFAULT_DATA };
        }
        return parsed;
    }
    saveData(DEFAULT_DATA);
    return { ...DEFAULT_DATA };
}

function saveData(data) {
    localStorage.setItem('skillPassportData', JSON.stringify(data));
}

function getData() {
    return loadData();
}

function updateData(updater) {
    const data = loadData();
    updater(data);
    saveData(data);
    return data;
}

function resetData() {
    localStorage.removeItem('skillPassportData');
    return loadData();
}

function showToast(message, type) {
    // Delegate to global toast API if available
    if (window.showToast) { return window.showToast(message, type); }

    // Fallback (standalone mockup implementation)
    let toast = document.getElementById('app-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'app-toast';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    toast.innerHTML = `<span class="material-symbols-outlined">check_circle</span> ${message}`;
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2500);
}
