// State management
let selectedSkills = new Set()
let parsedResumes = []
let uploadInProgress = false
let currentFiles = new DataTransfer() // Store current file selection
let lastToggledDetails = null // Track last toggled details row

// Debounce function for performance optimization
function debounce(func, wait) {
	let timeout
	return function executedFunction(...args) {
		const later = () => {
			clearTimeout(timeout)
			func(...args)
		}
		clearTimeout(timeout)
		timeout = setTimeout(later, wait)
	}
}

// Memoize function for caching results
function memoize(fn) {
	const cache = new Map()
	return (...args) => {
		const key = JSON.stringify(args)
		if (cache.has(key)) return cache.get(key)
		const result = fn(...args)
		cache.set(key, result)
		return result
	}
}

// DOM Elements
const overlay = document.getElementById('loading-overlay')
const form = document.getElementById('uploadForm')
const fileInput = document.getElementById('resumes')
const skillInput = document.getElementById('skillInput')
const skillTags = document.getElementById('skillTags')
const resultDiv = document.getElementById('result')
const parsedDataDiv = document.getElementById('parsed-data')
const totalCountSpan = document.getElementById('totalCount')
const matchCountSpan = document.getElementById('matchCount')
const showMatchingOnlyCheckbox = document.getElementById('showMatchingOnly')
const submitButton = document.querySelector('.submit-btn')
const selectedFilesContainer = document.getElementById('selectedFiles')

// Add new element for summary table
const summaryTableContainer = document.createElement('div')
summaryTableContainer.className = 'summary-table-container'
resultDiv.insertBefore(summaryTableContainer, parsedDataDiv)

// Hide loading overlay once the page loads
window.addEventListener('load', () => {
	if (overlay) overlay.style.display = 'none'
})

// Add drag and drop support
const fileLabel = document.querySelector('.file-label')

fileLabel.addEventListener('dragover', (e) => {
	e.preventDefault()
	e.stopPropagation()
	fileLabel.style.borderColor = '#3498db'
	fileLabel.style.background = '#edf2f7'
})

fileLabel.addEventListener('dragleave', (e) => {
	e.preventDefault()
	e.stopPropagation()
	fileLabel.style.borderColor = '#cbd5e0'
	fileLabel.style.background = '#e2e8f0'
})

fileLabel.addEventListener('drop', (e) => {
	e.preventDefault()
	e.stopPropagation()
	fileLabel.style.borderColor = '#cbd5e0'
	fileLabel.style.background = '#e2e8f0'

	const dt = new DataTransfer()
	let files = []

	// Handle both files and directory items
	if (e.dataTransfer.items) {
		files = [...e.dataTransfer.items]
			.filter((item) => item.kind === 'file')
			.map((item) => item.getAsFile())
	} else {
		files = [...e.dataTransfer.files]
	}

	if (files.length > 50) {
		alert('You can only select up to 50 files.')
		return
	}

	// Add dropped files to input
	files.forEach((file) => {
		if (file && allowed_extensions.includes(file.name.split('.').pop().toLowerCase())) {
			dt.items.add(file)
		}
	})

	fileInput.files = dt.files
	// Trigger change event manually
	fileInput.dispatchEvent(new Event('change'))
})

// Define allowed extensions
const allowed_extensions = ['pdf', 'docx']

// Optimize file handling
const handleFiles = (files) => {
	if (files.length + currentFiles.files.length > 50) {
		alert('You can only select up to 50 files in total.')
		return false
	}

	const newFiles = Array.from(files).filter((file) => {
		const isDuplicate = Array.from(currentFiles.files).some(
			(existing) =>
				existing.name === file.name &&
				existing.size === file.size &&
				existing.lastModified === file.lastModified
		)
		return !isDuplicate && allowed_extensions.includes(file.name.split('.').pop().toLowerCase())
	})

	newFiles.forEach((file) => currentFiles.items.add(file))
	return true
}

// Optimize file display update
const updateFileDisplay = () => {
	const fragment = document.createDocumentFragment()
	const files = Array.from(currentFiles.files)

	// Add file count header
	const fileCount = document.createElement('div')
	fileCount.className = 'file-count'
	fileCount.innerHTML = `
		<div>Selected Files <span>(${files.length}/50)</span></div>
		${
			files.length > 0
				? '<button type="button" onclick="clearAllFiles()" class="remove-file">Clear All</button>'
				: ''
		}
	`
	fragment.appendChild(fileCount)

	// Create container for file items
	const fileItemsContainer = document.createElement('div')
	fileItemsContainer.className = 'file-items-container'

	// Add individual file items
	files.forEach((file, index) => {
		const fileItem = document.createElement('div')
		fileItem.className = 'file-item'
		fileItem.innerHTML = `
			<span class="file-name" title="${file.name}">
				<i class="fas fa-file-alt"></i>
				${file.name}
				<small>(${formatFileSize(file.size)})</small>
			</span>
			<button type="button" class="remove-file" data-index="${index}" onclick="removeFile(${index})">
				<i class="fas fa-times"></i>
			</button>
		`
		fileItemsContainer.appendChild(fileItem)
	})

	fragment.appendChild(fileItemsContainer)
	selectedFilesContainer.innerHTML = ''
	selectedFilesContainer.appendChild(fragment)

	// Update submit button text and state
	submitButton.innerHTML =
		files.length > 0
			? `<i class="fas fa-robot"></i><span>Analyze ${files.length} Resume${
					files.length !== 1 ? 's' : ''
			  }</span>`
			: '<i class="fas fa-robot"></i><span>Analyze Resumes</span>'
	submitButton.disabled = files.length === 0
}

// Format file size
function formatFileSize(bytes) {
	if (bytes === 0) return '0 B'
	const k = 1024
	const sizes = ['B', 'KB', 'MB', 'GB']
	const i = Math.floor(Math.log(bytes) / Math.log(k))
	return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

// Remove individual file
function removeFile(index) {
	const dt = new DataTransfer()
	const files = Array.from(currentFiles.files)
	files.splice(index, 1)
	files.forEach((file) => dt.items.add(file))
	currentFiles = dt
	fileInput.files = currentFiles.files
	updateFileDisplay()
}

// Clear all files
function clearAllFiles() {
	currentFiles = new DataTransfer()
	fileInput.files = currentFiles.files
	updateFileDisplay()
}

// Memoized version of calculateMatchScore
const calculateMatchScore = memoize((resume) => {
	if (!resume || !resume.skills || !Array.isArray(resume.skills)) {
		console.error('Invalid resume data:', resume)
		return {
			score: 0,
			matches: [],
			missingSkills: Array.from(selectedSkills),
			hasAllRequiredSkills: false,
		}
	}

	if (selectedSkills.size === 0) {
		return { score: 0, matches: [], missingSkills: [], hasAllRequiredSkills: false }
	}

	const normalizedResumeSkills = new Set(
		resume.skills.map((s) =>
			String(s)
				.toLowerCase()
				.trim()
				.replace(/[-_\s]+/g, ' ')
		)
	)

	console.log('Resume Skills (normalized):', Array.from(normalizedResumeSkills))
	console.log('Required Skills:', Array.from(selectedSkills))

	const matches = []
	const missingSkills = []

	for (const requiredSkill of selectedSkills) {
		const normalizedSkill = requiredSkill
			.toLowerCase()
			.trim()
			.replace(/[-_\s]+/g, ' ')

		if (normalizedResumeSkills.has(normalizedSkill)) {
			matches.push(requiredSkill)
			console.log(`Found exact match for "${requiredSkill}"`)
			continue
		}

		const foundInSkill = Array.from(normalizedResumeSkills).find(
			(skill) => skill.includes(normalizedSkill) || normalizedSkill.includes(skill)
		)

		if (foundInSkill) {
			matches.push(requiredSkill)
			console.log(`Found partial match for "${requiredSkill}" in "${foundInSkill}"`)
		} else {
			missingSkills.push(requiredSkill)
			console.log(`No match found for "${requiredSkill}"`)
		}
	}

	const hasAllRequiredSkills = matches.length === selectedSkills.size
	const score = hasAllRequiredSkills
		? 100
		: Math.round((matches.length / selectedSkills.size) * 100)

	return {
		score,
		matches,
		missingSkills,
		hasAllRequiredSkills,
	}
})

// Optimize results display with virtual scrolling for large datasets
const displayResults = debounce((filterMatching = false) => {
	let displayedResumes = [...parsedResumes]
	if (filterMatching) {
		displayedResumes = displayedResumes.filter((r) => r.hasAllRequiredSkills)
	}

	// Sort by match status and matching skills count
	displayedResumes.sort((a, b) => {
		if (a.hasAllRequiredSkills !== b.hasAllRequiredSkills) {
			return b.hasAllRequiredSkills - a.hasAllRequiredSkills
		}
		return b.matchingSkills.length - a.matchingSkills.length
	})

	// Create summary table if there are skills selected
	if (selectedSkills.size > 0) {
		const tableHTML = generateSummaryTable(displayedResumes)
		summaryTableContainer.innerHTML = tableHTML
	} else {
		summaryTableContainer.innerHTML = ''
	}

	parsedDataDiv.style.display = 'none'
}, 100)

// Separate table generation for better maintainability
function generateSummaryTable(displayedResumes) {
	return `
		<div class="summary-table">
			<h3>Skills Matching Summary</h3>
			<table>
				<thead>
					<tr>
						<th>Resume File</th>
						<th>Candidate Name</th>
						<th>Contact Info</th>
						<th>Matching Skills (${selectedSkills.size} Required)</th>
						<th>Match Score</th>
						<th>Missing Skills</th>
						<th>Actions</th>
					</tr>
				</thead>
				<tbody>
					${displayedResumes.map(generateTableRow).join('')}
				</tbody>
			</table>
		</div>
	`
}

// Separate row generation for better maintainability
function generateTableRow(resume) {
	if (!resume) return ''

	return `
		<tr class="${resume.hasAllRequiredSkills ? 'full-match' : ''}">
			<td class="filename">${resume.filename || 'N/A'}</td>
			<td>${resume.name || 'Unknown'}</td>
			<td>
				${resume.email ? `<div>📧 ${resume.email}</div>` : ''}
				${resume.phone ? `<div>📱 ${resume.phone}</div>` : ''}
			</td>
			<td>
				${
					(resume.matchingSkills || []).length > 0
						? `<span class="matching-skills">${resume.matchingSkills.join(', ')}</span>`
						: '<span class="no-match">None</span>'
				}
			</td>
			<td class="match-count">
				<span class="${resume.hasAllRequiredSkills ? 'perfect-match' : ''}">
					${(resume.matchingSkills || []).length} / ${selectedSkills.size}
				</span>
			</td>
			<td>
				${
					(resume.missingSkills || []).length > 0
						? `<span class="missing-skills">${resume.missingSkills.join(', ')}</span>`
						: '<span class="no-missing">None</span>'
				}
			</td>
			<td>
				<button class="view-details-btn" onclick="toggleResumeDetails('${resume.filename}')">
					View Details
				</button>
			</td>
		</tr>
		<tr id="details-${resume.filename.replace(
			/\./g,
			'-'
		)}" class="resume-details" style="display: none;">
			<td colspan="7">
				<div class="details-content">
					${generateDetailsContent(resume)}
				</div>
			</td>
		</tr>
	`
}

// Separate details content generation
function generateDetailsContent(resume) {
	if (!resume) return ''

	return `
		<div class="section">
			<h4>Education</h4>
			<ul>
				${(resume.education || []).map((edu) => `<li>${edu.degree || edu}</li>`).join('')}
			</ul>
		</div>
		<div class="section">
			<h4>Work Experience</h4>
			<ul>
				${(resume.work_experience || []).map((exp) => `<li>${exp.description || exp}</li>`).join('')}
			</ul>
		</div>
		<div class="section">
			<h4>All Skills</h4>
			<div class="skills-list">
				${(resume.skills || [])
					.map(
						(skill) => `
					<span class="skill-tag ${
						(resume.matchingSkills || []).includes(skill.toLowerCase()) ? 'matching' : ''
					}">${skill}</span>
				`
					)
					.join('')}
			</div>
		</div>
		${
			resume.ai_summary
				? `
			<div class="section">
				<h4>AI Summary</h4>
				<p>${resume.ai_summary}</p>
			</div>
		`
				: ''
		}
	`
}

// Optimize details toggle with animation and cleanup
function toggleResumeDetails(filename) {
	const detailsRow = document.getElementById(`details-${filename.replace(/\./g, '-')}`)

	// Close previously opened details if different from current
	if (lastToggledDetails && lastToggledDetails !== detailsRow) {
		lastToggledDetails.style.display = 'none'
	}

	// Toggle current details with smooth animation
	if (detailsRow.style.display === 'none') {
		detailsRow.style.display = 'table-row'
		detailsRow.style.opacity = '0'
		setTimeout(() => {
			detailsRow.style.transition = 'opacity 0.3s ease-in-out'
			detailsRow.style.opacity = '1'
		}, 10)
		lastToggledDetails = detailsRow
	} else {
		detailsRow.style.opacity = '0'
		setTimeout(() => {
			detailsRow.style.display = 'none'
			lastToggledDetails = null
		}, 300)
	}
}

// Event Listeners with optimized handlers
window.addEventListener('load', () => {
	if (overlay) overlay.style.display = 'none'
})

fileInput.addEventListener('change', function () {
	if (handleFiles(this.files)) {
		this.files = currentFiles.files
		updateFileDisplay()
	}
})

skillInput.addEventListener('keydown', (e) => {
	if (e.key === 'Enter') {
		e.preventDefault()
		const skill = skillInput.value.trim().toLowerCase()
		if (skill && !selectedSkills.has(skill)) {
			console.log('Adding skill:', skill)
			selectedSkills.add(skill)
			addSkillTag(skill)
			skillInput.value = ''
			updateMatchingScores()
		}
	}
})

form.addEventListener('submit', async function (e) {
	e.preventDefault()
	if (uploadInProgress) return

	const files = currentFiles.files
	if (!files.length) {
		alert('Please select at least one resume to analyze.')
		return
	}

	uploadInProgress = true
	overlay.style.display = 'flex'
	resultDiv.style.display = 'none'
	parsedResumes = []
	submitButton.disabled = true

	try {
		const results = await processFiles(files)
		parsedResumes = results
		resultDiv.style.display = 'block'
		updateMatchingScores()
	} catch (error) {
		alert('Error processing resumes: ' + error.message)
	} finally {
		overlay.style.display = 'none'
		submitButton.disabled = false
		uploadInProgress = false
	}
})

showMatchingOnlyCheckbox.addEventListener('change', function () {
	displayResults(this.checked)
})

// Optimize file processing with batching
async function processFiles(files) {
	const results = []
	const batchSize = 5

	for (let i = 0; i < files.length; i += batchSize) {
		const batch = Array.from(files).slice(i, i + batchSize)
		const batchPromises = batch.map(async (file) => {
			const formData = new FormData()
			formData.append('resume', file)

			submitButton.textContent = `Processing ${file.name}...`
			const response = await fetch('/upload', {
				method: 'POST',
				body: formData,
			})

			if (!response.ok) {
				const error = await response.json()
				throw new Error(error.error || `Failed to process ${file.name}`)
			}

			const data = await response.json()

			// Extract the actual resume data from the response
			if (!data.results || !Array.isArray(data.results) || data.results.length === 0) {
				throw new Error(`No valid results found for ${file.name}`)
			}

			// Get the first result since we're uploading one file at a time
			const result = data.results[0]

			// Ensure result has all required fields
			return {
				filename: file.name,
				name: result.name || 'Unknown',
				email: result.email || '',
				phone: result.phone || '',
				education: result.education || [],
				work_experience: result.work_experience || [],
				skills: result.skills || [],
				ai_summary: result.ai_summary || '',
				matchingSkills: [],
				missingSkills: [],
				hasAllRequiredSkills: false,
			}
		})

		try {
			const batchResults = await Promise.all(batchPromises)
			results.push(...batchResults)
		} catch (error) {
			console.error('Error processing batch:', error)
			// Continue with other batches even if one fails
		}
	}

	submitButton.textContent = 'Analysis Complete!'
	setTimeout(() => {
		submitButton.textContent = `Analyze ${files.length} Resume${files.length !== 1 ? 's' : ''}`
	}, 2000)

	return results
}

function addSkillTag(skill) {
	const tag = document.createElement('div')
	tag.className = 'skill-tag'
	tag.innerHTML = `
        ${skill}
        <button type="button" onclick="removeSkill('${skill}')">&times;</button>
    `
	skillTags.appendChild(tag)
}

function removeSkill(skill) {
	selectedSkills.delete(skill.toLowerCase())
	updateSkillTags()
	updateMatchingScores()
}

function updateSkillTags() {
	skillTags.innerHTML = ''
	selectedSkills.forEach(addSkillTag)
}

function getScoreClass(score) {
	// Since we now only have matching (100) or non-matching (0)
	return score === 100 ? 'high' : 'low'
}

function updateMatchingScores() {
	if (!parsedResumes.length) return

	parsedResumes.forEach((resume) => {
		const { score, matches, missingSkills, hasAllRequiredSkills } = calculateMatchScore(resume)
		resume.matchScore = score
		resume.matchingSkills = matches
		resume.missingSkills = missingSkills
		resume.hasAllRequiredSkills = hasAllRequiredSkills
	})

	const matchingResumes = parsedResumes.filter((r) => r.hasAllRequiredSkills)
	totalCountSpan.textContent = parsedResumes.length
	matchCountSpan.textContent = matchingResumes.length

	displayResults()
}
