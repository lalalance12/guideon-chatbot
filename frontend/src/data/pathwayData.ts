import { CareerPathway, SkillPathway } from "../types/pathways";

// Sample Skill Pathways
export const skillPathways: SkillPathway[] = [
  {
    id: "data-analysis",
    title: "Data Analysis",
    description: "Learn essential data analysis skills including statistics, visualization, and interpretation",
    courses: [
      {
        id: "basic-stats",
        title: "Statistics Fundamentals",
        description: "Learn the foundations of statistics for data analysis",
        duration: "4 weeks",
        level: "Beginner"
      },
      {
        id: "data-viz",
        title: "Data Visualization",
        description: "Create effective visualizations to communicate insights",
        duration: "3 weeks",
        level: "Intermediate"
      },
      {
        id: "adv-analysis",
        title: "Advanced Data Analysis",
        description: "Master complex analytical techniques",
        duration: "6 weeks",
        level: "Advanced"
      },
    ]
  },
  {
    id: "machine-learning",
    title: "Machine Learning",
    description: "Build AI models to solve business problems with machine learning techniques",
    courses: [
      {
        id: "ml-intro",
        title: "Introduction to Machine Learning",
        description: "Understand the fundamentals of machine learning algorithms",
        duration: "5 weeks",
        level: "Beginner"
      },
      {
        id: "supervised-learning",
        title: "Supervised Learning",
        description: "Build and evaluate supervised learning models",
        duration: "6 weeks",
        level: "Intermediate"
      },
      {
        id: "deep-learning",
        title: "Deep Learning",
        description: "Neural networks and deep learning architectures",
        duration: "8 weeks",
        level: "Advanced"
      },
    ]
  },
  {
    id: "data-engineering",
    title: "Data Engineering",
    description: "Learn to build and maintain data pipelines and infrastructure",
    courses: [
      {
        id: "data-storage",
        title: "Data Storage Systems",
        description: "Understand various database systems and their use cases",
        duration: "4 weeks",
        level: "Beginner"
      },
      {
        id: "data-pipelines",
        title: "Data Pipeline Architecture",
        description: "Design and implement efficient data pipelines",
        duration: "5 weeks",
        level: "Intermediate"
      },
      {
        id: "big-data",
        title: "Big Data Processing",
        description: "Work with distributed computing frameworks",
        duration: "6 weeks",
        level: "Advanced"
      },
    ]
  },
  {
    id: "cloud-computing",
    title: "Cloud Computing",
    description: "Master cloud platforms and services for modern applications",
    courses: [
      {
        id: "cloud-basics",
        title: "Cloud Fundamentals",
        description: "Introduction to cloud computing concepts",
        duration: "3 weeks",
        level: "Beginner"
      },
      {
        id: "cloud-services",
        title: "Cloud Services and Applications",
        description: "Deploy and manage applications in the cloud",
        duration: "4 weeks",
        level: "Intermediate"
      },
      {
        id: "cloud-architecture",
        title: "Cloud Architecture Design",
        description: "Design scalable and resilient cloud systems",
        duration: "6 weeks",
        level: "Advanced"
      },
    ]
  },
];

// Sample Career Pathways
export const careerPathways: CareerPathway[] = [
  {
    id: "data-scientist",
    title: "Data Scientist",
    description: "Build a career extracting insights from data and creating predictive models",
    field: "Data Science",
    levels: [
      {
        level: "Associate",
        title: "Junior Data Scientist",
        requiredSkills: [
          {
            id: "python-basics",
            name: "Python Programming",
            description: "Fundamental Python programming skills",
            level: "Intermediate"
          },
          {
            id: "basic-stats",
            name: "Basic Statistics",
            description: "Understanding of statistical concepts",
            level: "Beginner"
          },
          {
            id: "data-cleaning",
            name: "Data Cleaning",
            description: "Ability to clean and preprocess data",
            level: "Beginner"
          }
        ]
      },
      {
        level: "Professional",
        title: "Data Scientist",
        requiredSkills: [
          {
            id: "adv-ml",
            name: "Machine Learning",
            description: "Building and evaluating ML models",
            level: "Intermediate"
          },
          {
            id: "data-viz",
            name: "Data Visualization",
            description: "Creating effective data visualizations",
            level: "Intermediate"
          },
          {
            id: "sql",
            name: "SQL",
            description: "Advanced database querying",
            level: "Intermediate"
          }
        ]
      },
      {
        level: "Senior Professional",
        title: "Senior Data Scientist",
        requiredSkills: [
          {
            id: "adv-ml-models",
            name: "Advanced ML Models",
            description: "Complex machine learning models",
            level: "Advanced"
          },
          {
            id: "domain-expertise",
            name: "Domain Expertise",
            description: "Deep understanding of business domain",
            level: "Advanced"
          },
          {
            id: "exp-design",
            name: "Experimental Design",
            description: "Design and analyze experiments",
            level: "Advanced"
          }
        ]
      },
      {
        level: "Director",
        title: "Director of Data Science",
        requiredSkills: [
          {
            id: "team-leadership",
            name: "Team Leadership",
            description: "Leading and developing data science teams",
            level: "Expert"
          },
          {
            id: "strategy",
            name: "Strategic Planning",
            description: "Creating data strategy aligned with business",
            level: "Expert"
          },
          {
            id: "exec-comm",
            name: "Executive Communication",
            description: "Communicating complex insights to executives",
            level: "Advanced"
          }
        ]
      }
    ]
  },
  {
    id: "data-engineer",
    title: "Data Engineer",
    description: "Progress through data engineering roles building robust data infrastructure",
    field: "Data Engineering",
    levels: [
      {
        level: "Associate",
        title: "Junior Data Engineer",
        requiredSkills: [
          {
            id: "sql-basics",
            name: "SQL Fundamentals",
            description: "Basic database querying",
            level: "Intermediate"
          },
          {
            id: "etl-basics",
            name: "ETL Basics",
            description: "Understanding of ETL processes",
            level: "Beginner"
          },
          {
            id: "python-basics",
            name: "Python Basics",
            description: "Basic scripting in Python",
            level: "Beginner"
          }
        ]
      },
      {
        level: "Professional",
        title: "Data Engineer",
        requiredSkills: [
          {
            id: "adv-databases",
            name: "Advanced Databases",
            description: "Working with various database systems",
            level: "Intermediate"
          },
          {
            id: "data-pipelines",
            name: "Data Pipeline Development",
            description: "Building reliable data pipelines",
            level: "Intermediate"
          },
          {
            id: "cloud-platforms",
            name: "Cloud Platforms",
            description: "Working with cloud data services",
            level: "Intermediate"
          }
        ]
      },
      {
        level: "Senior Professional",
        title: "Senior Data Engineer",
        requiredSkills: [
          {
            id: "distributed-systems",
            name: "Distributed Systems",
            description: "Building and maintaining distributed data systems",
            level: "Advanced"
          },
          {
            id: "data-architecture",
            name: "Data Architecture",
            description: "Designing scalable data architectures",
            level: "Advanced"
          },
          {
            id: "performance-tuning",
            name: "Performance Optimization",
            description: "Optimizing data system performance",
            level: "Advanced"
          }
        ]
      },
      {
        level: "Manager",
        title: "Data Engineering Manager",
        requiredSkills: [
          {
            id: "team-management",
            name: "Team Management",
            description: "Leading data engineering teams",
            level: "Advanced"
          },
          {
            id: "project-planning",
            name: "Project Planning",
            description: "Planning and executing complex data projects",
            level: "Advanced"
          },
          {
            id: "stakeholder-management",
            name: "Stakeholder Management",
            description: "Managing stakeholder expectations",
            level: "Intermediate"
          }
        ]
      }
    ]
  },
  {
    id: "analytics-engineer",
    title: "Analytics Engineer",
    description: "Build a career bridging data engineering and analytics",
    field: "Data Analytics",
    levels: [
      {
        level: "Associate",
        title: "Junior Analytics Engineer",
        requiredSkills: [
          {
            id: "sql-basics",
            name: "SQL",
            description: "Writing efficient SQL queries",
            level: "Intermediate"
          },
          {
            id: "data-modeling",
            name: "Data Modeling Basics",
            description: "Creating basic data models",
            level: "Beginner"
          },
          {
            id: "bi-tools",
            name: "BI Tools",
            description: "Using business intelligence tools",
            level: "Beginner"
          }
        ]
      },
      {
        level: "Professional",
        title: "Analytics Engineer",
        requiredSkills: [
          {
            id: "adv-sql",
            name: "Advanced SQL",
            description: "Complex SQL and query optimization",
            level: "Advanced"
          },
          {
            id: "dbt",
            name: "Data Build Tool",
            description: "Using dbt for transformations",
            level: "Intermediate"
          },
          {
            id: "data-warehouse",
            name: "Data Warehousing",
            description: "Modern data warehouse concepts",
            level: "Intermediate"
          }
        ]
      },
      {
        level: "Senior Professional",
        title: "Senior Analytics Engineer",
        requiredSkills: [
          {
            id: "metrics-layer",
            name: "Metrics Layer",
            description: "Building robust metrics layers",
            level: "Advanced"
          },
          {
            id: "data-governance",
            name: "Data Governance",
            description: "Implementing data governance practices",
            level: "Advanced"
          },
          {
            id: "data-ops",
            name: "DataOps",
            description: "Automating data workflows",
            level: "Advanced"
          }
        ]
      },
      {
        level: "Manager",
        title: "Analytics Engineering Manager",
        requiredSkills: [
          {
            id: "team-leadership",
            name: "Team Leadership",
            description: "Leading analytics engineering teams",
            level: "Advanced"
          },
          {
            id: "analytics-strategy",
            name: "Analytics Strategy",
            description: "Developing analytics strategy",
            level: "Advanced"
          },
          {
            id: "cross-func-collab",
            name: "Cross-functional Collaboration",
            description: "Working across teams and functions",
            level: "Advanced"
          }
        ]
      }
    ]
  }
];
