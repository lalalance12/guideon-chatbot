const fs = require('fs');
const path = require('path');

/**
 * Determines skill level based on job grade
 * @param {string} grade - The job grade
 * @returns {string} The corresponding skill level
 */
function determineSkillLevel(grade) {
  switch(grade) {
    case 'Associate': return 'Beginner';
    case 'Senior Associate': return 'Intermediate';
    case 'Professional': return 'Intermediate';
    case 'Senior Professional / Supervisor': return 'Advanced';
    case 'Manager': case 'Senior Manager': return 'Advanced';
    case 'Director': case 'Senior Director': return 'Expert';
    case 'C Level': return 'Expert';
    default: return 'Intermediate';
  }
}

/**
 * Cleans a role name by trimming spaces and removing extra spaces
 * @param {string} role - The role name
 * @returns {string} The cleaned role name
 */
function cleanRoleName(role) {
  return role ? role.trim().replace(/\s+/g, ' ') : '';
}

/**
 * Builds a domain-based career map
 * @param {Object} careerMap - The career map data
 * @returns {Object} Map of domain-specific career paths
 */
function buildDomainCareerPaths(careerMap) {
  const domainPaths = {};
  
  // Process each domain
  careerMap.domains.forEach(domain => {
    // Store roles in order from entry-level to senior
    const sortedRoles = [...domain.roles]
      .filter(role => role.role && role.role.trim()) // Remove roles without names
      .sort((a, b) => {
        const gradeOrder = [
          'Associate', 'Senior Associate', 'Professional', 
          'Senior Professional / Supervisor', 'Manager', 'Senior Manager',
          'Director', 'Senior Director', 'C Level'
        ];
        return gradeOrder.indexOf(a.grade) - gradeOrder.indexOf(b.grade);
      })
      .map(role => ({
        role: cleanRoleName(role.role),
        grade: role.grade
      }));
    
    domainPaths[domain.name] = sortedRoles;
  });
  
  return domainPaths;
}

/**
 * Creates a map of roles to their domains
 * @param {Object} careerMap - The career map data
 * @returns {Object} Map of roles to domains
 */
function buildRoleToDomainMap(careerMap) {
  const roleToDomain = {};
  
  careerMap.domains.forEach(domain => {
    domain.roles.forEach(role => {
      if (role.role) {
        const cleanRole = cleanRoleName(role.role);
        roleToDomain[cleanRole] = domain.name;
      }
    });
  });
  
  return roleToDomain;
}

/**
 * Gets the career path for a specific role within its domain
 * @param {string} roleName - The target role name
 * @param {Object} domainPaths - Map of domain-specific career paths
 * @param {Object} roleToDomain - Map of roles to domains
 * @returns {Array} The career path for the role
 */
function getDomainCareerPath(roleName, domainPaths, roleToDomain) {
  const domain = roleToDomain[roleName];
  
  if (!domain || !domainPaths[domain]) {
    return [{ role: roleName, grade: 'Unknown' }];
  }
  
  const domainPath = domainPaths[domain];
  const roleIndex = domainPath.findIndex(r => r.role === roleName);
  
  // If role found in domain path, return all roles up to and including this role
  if (roleIndex >= 0) {
    return domainPath.slice(0, roleIndex + 1);
  }
  
  // If role not found in domain path, return just the role
  return [{ role: roleName, grade: 'Unknown' }];
}

/**
 * Extracts all unique functional skills from job info
 * @param {Array} jobInfo - Job information data
 * @returns {Array} Array of unique functional skills
 */
function extractUniqueSkills(jobInfo) {
  const uniqueSkills = new Set();
  
  jobInfo.forEach(job => {
    if (job && job.functional_skills && Array.isArray(job.functional_skills)) {
      job.functional_skills.forEach(skill => {
        if (skill && typeof skill === 'string' && skill.trim()) {
          uniqueSkills.add(skill.trim());
        }
      });
    }
  });
  
  return Array.from(uniqueSkills);
}

/**
 * Maps job titles that require a specific skill
 * @param {Array} jobInfo - Job information data
 * @returns {Object} Map of skills to job titles requiring them
 */
function mapSkillsToJobs(jobInfo) {
  const skillToJobs = {};
  
  jobInfo.forEach(job => {
    if (job && job.job_title && job.functional_skills && Array.isArray(job.functional_skills)) {
      job.functional_skills.forEach(skill => {
        if (skill && typeof skill === 'string' && skill.trim()) {
          const cleanedSkill = skill.trim();
          if (!skillToJobs[cleanedSkill]) {
            skillToJobs[cleanedSkill] = [];
          }
          skillToJobs[cleanedSkill].push(job.job_title);
        }
      });
    }
  });
  
  return skillToJobs;
}

/**
 * Generates skill pathways from functional skills in job info
 * @param {Array} jobInfo - Job information data
 * @returns {Array} Skill pathways
 */
function generateSkillPathways(jobInfo) {
  const skills = extractUniqueSkills(jobInfo);
  const skillToJobs = mapSkillsToJobs(jobInfo);
  
  console.log(`Found ${skills.length} unique functional skills`);
  
  return skills.map((skill, index) => {
    const skillId = skill.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    
    // Create courses for this skill (representing different levels)
    const courses = [
      {
        id: `${skillId}-beginner`,
        title: `${skill} Fundamentals`,
        description: `Learn the foundations of ${skill}`,
        duration: "4 weeks",
        level: "Beginner"
      },
      {
        id: `${skillId}-intermediate`,
        title: `Intermediate ${skill}`,
        description: `Build on your ${skill} knowledge with more advanced concepts`,
        duration: "6 weeks",
        level: "Intermediate"
      },
      {
        id: `${skillId}-advanced`,
        title: `Advanced ${skill}`,
        description: `Master complex ${skill} techniques and applications`,
        duration: "8 weeks",
        level: "Advanced"
      }
    ];
    
    // Use the jobs requiring this skill to enrich the description
    const relatedJobs = skillToJobs[skill] || [];
    const jobsDescription = relatedJobs.length > 0 
      ? `Needed for roles such as ${relatedJobs.slice(0, 3).join(', ')}${relatedJobs.length > 3 ? ' and more' : ''}`
      : '';
    
    return {
      id: skillId,
      title: skill,
      description: `Master ${skill} skills for data and AI careers. ${jobsDescription}`,
      courses
    };
  });
}

/**
 * Generates career pathways from career map and job info
 * @param {Object} careerMap - The career map data
 * @param {Array} jobInfo - Job information data
 * @returns {Array} Career pathways
 */
function generateCareerPathways(careerMap, jobInfo) {
  const pathways = [];
  
  // Build domain-based career paths and role-to-domain mapping
  const domainPaths = buildDomainCareerPaths(careerMap);
  const roleToDomain = buildRoleToDomainMap(careerMap);
  
  // Get all job titles from job info that have matching roles in the career map
  const jobTitles = jobInfo
    .filter(job => job && job.job_title && roleToDomain[cleanRoleName(job.job_title)])
    .map(job => cleanRoleName(job.job_title));
  
  console.log(`Found ${jobTitles.length} job titles with career paths`);
  
  // Process each job title
  jobTitles.forEach(jobTitle => {
    // Get full career path for this job title within its domain
    const careerPath = getDomainCareerPath(jobTitle, domainPaths, roleToDomain);
    const domain = roleToDomain[jobTitle] || 'General';
    
    // Get job details
    const jobDetails = jobInfo.find(job => 
      cleanRoleName(job.job_title) === jobTitle);
    
    if (!jobDetails) {
      console.log(`No job details found for ${jobTitle}`);
      return;
    }
    
    // Create pathway object
    const pathway = {
      id: jobTitle.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
      title: jobTitle,
      description: jobDetails.description || `Career pathway to ${jobTitle}`,
      field: domain,
      levels: []
    };
    
    // Add each role in the path as a level
    careerPath.forEach(({ role, grade }) => {
      // Get details for this role
      const roleDetails = jobInfo.find(job => 
        cleanRoleName(job.job_title) === role);
      
      if (!roleDetails) {
        console.log(`No role details found for ${role}`);
        return;
      }
      
      const requiredSkills = [];
      
      // Extract functional skills (up to 10 to avoid too many)
      if (roleDetails.functional_skills && roleDetails.functional_skills.length > 0) {
        roleDetails.functional_skills.slice(0, 10).forEach((skill, index) => {
          if (skill) {
            requiredSkills.push({
              id: `${pathway.id}-${grade.toLowerCase().replace(/\s+/g, '-')}-skill-${index}`,
              name: skill,
              description: `Proficiency in ${skill}`,
              level: "Placeholder" // Use placeholder as requested
            });
          }
        });
      }
      
      // Add level to pathway
      pathway.levels.push({
        level: grade,
        title: role,
        description: roleDetails.description || `Position on the path to ${jobTitle}`,
        requiredSkills: requiredSkills.length > 0 ? requiredSkills : [
          {
            id: `${pathway.id}-${grade.toLowerCase().replace(/\s+/g, '-')}-default-skill`,
            name: "Domain Knowledge",
            description: `Knowledge required for ${role}`,
            level: "Placeholder"
          }
        ]
      });
    });
    
    // Only add pathways with meaningful levels
    if (pathway.levels.length > 0) {
      pathways.push(pathway);
    }
  });
  
  return pathways;
}

// Main execution
try {
  // Define project root directory (3 levels up from current script location)
  const projectRoot = path.resolve(__dirname, '../../..');
  
  // Load your data with absolute paths
  const careerMapPath = path.join(projectRoot, 'backend', 'api', 'data-sample', 'career_map.json');
  const jobInfoPath = path.join(projectRoot, 'backend', 'api', 'data', 'roles', 'extracted_job_info.json');
  
  console.log('Reading career map from:', careerMapPath);
  console.log('Reading job info from:', jobInfoPath);
  
  let careerMapData, jobInfoData;
  
  try {
    careerMapData = JSON.parse(fs.readFileSync(careerMapPath, 'utf8'));
  } catch (error) {
    console.error(`Error reading career map: ${error.message}`);
    process.exit(1);
  }
  
  try {
    jobInfoData = JSON.parse(fs.readFileSync(jobInfoPath, 'utf8'));
  } catch (error) {
    console.error(`Error reading job info: ${error.message}`);
    process.exit(1);
  }

  // Generate career pathways and skill pathways
  const careerPathways = generateCareerPathways(careerMapData, jobInfoData);
  const skillPathways = generateSkillPathways(jobInfoData);
  
  console.log(`Generated ${careerPathways.length} career pathways`);
  console.log(`Generated ${skillPathways.length} skill pathways`);

  // Path to pathwayData.ts
  const pathwayDataPath = path.join(__dirname, 'pathwayData.ts');
  
  // Create new content with both career and skill pathways
  const newContent = `import { CareerPathway, SkillPathway } from "../types/pathways";

// Skill Pathways generated from functional skills (${skillPathways.length} pathways)
export const skillPathways: SkillPathway[] = ${JSON.stringify(skillPathways, null, 2)};

// Career Pathways generated from career map data (${careerPathways.length} pathways)
export const careerPathways: CareerPathway[] = ${JSON.stringify(careerPathways, null, 2)};
`;

  // Write the new content
  fs.writeFileSync(pathwayDataPath, newContent, 'utf8');
  console.log('pathwayData.ts updated successfully!');
  
  // Log sample of generated pathways
  if (careerPathways.length > 0) {
    console.log('\nSample career pathway:');
    console.log(`Title: ${careerPathways[0].title}`);
    console.log(`Field: ${careerPathways[0].field}`);
    console.log(`Levels: ${careerPathways[0].levels.length}`);
  }
  
  if (skillPathways.length > 0) {
    console.log('\nSample skill pathway:');
    console.log(`Title: ${skillPathways[0].title}`);
    console.log(`Courses: ${skillPathways[0].courses.length}`);
  }
  
} catch (error) {
  console.error('Error generating pathways:', error);
}