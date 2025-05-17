from api.models import Course

def store_scraped_course(course_data, skill=None):
    """
    Store a scraped course in the database.
    
    Args:
        course_data (dict): Dictionary containing course information
        skill (str, optional): Related skill name
    
    Returns:
        Course: The created or updated Course object
    """
    # Extract core fields
    title = course_data.get('course_title') or course_data.get('title')
    provider = course_data.get('course_provider') or course_data.get('provider')
    url = course_data.get('course_url') or course_data.get('url')
    description = course_data.get('course_description') or course_data.get('description')
    rating = course_data.get('course_rating') or course_data.get('rating')
    
    if not (title and provider and url):
        raise ValueError("Course data missing required fields: title, provider, and url")
    
    # Check for existing course to avoid duplicates
    existing_course = Course.objects.filter(url=url).first()
    
    # Prepare metadata - now only containing additional data
    metadata = {}
    
    # Add any other attributes from course_data that aren't core fields
    for key, value in course_data.items():
        if key not in ['course_title', 'title', 'course_provider', 'provider', 'course_url', 'url', 'course_description', 'description', 'course_rating', 'rating']:
            metadata[key] = value
    
    # Add skill if provided
    if skill:
        metadata['skill'] = skill
    
    if existing_course:
        # Update existing course
        existing_course.title = title
        existing_course.provider = provider
        existing_course.description = description
        existing_course.rating = rating if rating is not None else existing_course.rating
        
        # Update metadata (merge with existing)
        existing_metadata = existing_course.metadata or {}
        existing_metadata.update(metadata)
        existing_course.metadata = existing_metadata
        
        existing_course.save()
        return existing_course
    else:
        # Create new course
        return Course.objects.create(
            title=title,
            provider=provider,
            url=url,
            description=description,
            rating=rating,
            metadata=metadata
        )
